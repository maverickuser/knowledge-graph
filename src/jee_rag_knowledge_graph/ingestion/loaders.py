"""Local source loading helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile
import json

from ..domain.models import SourceDocument, make_source_document
from ..exceptions import ExtractionError, UnsupportedSourceFormatError


@dataclass(frozen=True, slots=True)
class LocalSourceRead:
    source_document: SourceDocument
    raw_text: str


def _detect_source_type(path: Path, explicit_source_type: str | None = None) -> str:
    if explicit_source_type:
        return explicit_source_type.lower()

    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".txt", ".rst"}:
        return "text"
    if suffix in {".json"}:
        return "json"
    if suffix in {".csv"}:
        return "csv"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".docx"}:
        return "docx"
    if suffix in {".pdf"}:
        return "pdf"
    return "text"


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


def _read_html(path: Path) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.get_text()


def _read_json(path: Path) -> str:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(parsed, indent=2, sort_keys=True)


def _read_csv(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_docx(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ExtractionError(f"failed to read DOCX source: {path}") from exc

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        runs = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _get_pdf_reader_class() -> type:
    last_error: Exception | None = None
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = import_module(module_name)
            return getattr(module, "PdfReader")
        except Exception as exc:  # pragma: no cover - exercised through fallback tests
            last_error = exc

    raise UnsupportedSourceFormatError(
        "PDF support requires pypdf or PyPDF2 to be installed locally"
    ) from last_error


def _read_pdf_with_pdftotext(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if executable is None:
        raise UnsupportedSourceFormatError(
            "PDF support requires pypdf, PyPDF2, or the pdftotext command to be installed locally"
        )

    runtime = Path(tempfile.gettempdir()) / "jee-rag-knowledge-graph-pdftotext"
    log_dir = runtime / "miktex" / "log"
    data_dir = runtime / "miktex" / "data"
    config_dir = runtime / "miktex" / "config"
    for directory in (log_dir, data_dir, config_dir):
        directory.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    for key in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "TEMP", "TMP"):
        env[key] = str(runtime)
    env["MIKTEX_LOG_DIR"] = str(log_dir)
    env["MIKTEX_USERDATA"] = str(data_dir)
    env["MIKTEX_USERCONFIG"] = str(config_dir)
    env["MIKTEX_COMMONDATA"] = str(data_dir)
    env["MIKTEX_COMMONCONFIG"] = str(config_dir)

    completed = subprocess.run(  # noqa: S603
        [executable, "-layout", "-enc", "UTF-8", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise ExtractionError(f"failed to read PDF source: {path}{f': {stderr}' if stderr else ''}")
    return completed.stdout.replace("\f", "\n")


def _read_pdf(path: Path) -> str:
    try:
        reader_class = _get_pdf_reader_class()
        reader = reader_class(str(path))
        pages: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                pages.append(extracted)
        return "\n".join(pages)
    except UnsupportedSourceFormatError:
        return _read_pdf_with_pdftotext(path)
    except Exception as exc:
        try:
            return _read_pdf_with_pdftotext(path)
        except UnsupportedSourceFormatError:
            raise ExtractionError(f"failed to read PDF source: {path}") from exc


def read_source_text(path: str | Path, source_type: str | None = None) -> str:
    """Read a local source file into text."""

    source_path = Path(path)
    if not source_path.exists():
        raise ExtractionError(f"source file does not exist: {source_path}")

    resolved_source_type = _detect_source_type(source_path, source_type)
    if resolved_source_type in {"text", "markdown"}:
        return _read_text_file(source_path)
    if resolved_source_type == "html":
        return _read_html(source_path)
    if resolved_source_type == "json":
        return _read_json(source_path)
    if resolved_source_type == "csv":
        return _read_csv(source_path)
    if resolved_source_type == "docx":
        return _read_docx(source_path)
    if resolved_source_type == "pdf":
        return _read_pdf(source_path)

    return _read_text_file(source_path)


def load_local_source(
    path: str | Path,
    *,
    title: str | None = None,
    version: str = "1",
    source_type: str | None = None,
) -> LocalSourceRead:
    """Load a local source file and create a provenance-bearing source record."""

    source_path = Path(path).resolve()
    raw_text = read_source_text(source_path, source_type=source_type)
    checksum = sha256(source_path.read_bytes()).hexdigest()
    resolved_source_type = _detect_source_type(source_path, source_type)
    source_document = make_source_document(
        local_path=source_path,
        source_type=resolved_source_type,
        title=title or source_path.stem,
        version=version,
        checksum=checksum,
    )
    return LocalSourceRead(source_document=source_document, raw_text=raw_text)
