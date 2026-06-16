from __future__ import annotations

import tempfile
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from zipfile import ZipFile

from unittest import TestCase

import knowledge_graph.ingestion.loaders as loaders
from knowledge_graph.exceptions import ExtractionError, UnsupportedSourceFormatError
from knowledge_graph.ingestion.loaders import load_local_source, read_source_text
from knowledge_graph.ingestion.normalize import normalize_source_document
from tests.sample_data import SAMPLE_SYLLABUS


class IngestionTests(TestCase):
    def _write_docx_fixture(self, path: Path, paragraphs: tuple[str, ...]) -> None:
        body = "".join(
            f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}<w:sectPr/></w:body>"
            "</w:document>"
        )
        with ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)

    def test_load_and_normalize_fixture(self) -> None:
        read = load_local_source(SAMPLE_SYLLABUS, title="Sample Syllabus", version="1")
        normalized = normalize_source_document(read.source_document, read.raw_text, version="1")

        self.assertEqual(read.source_document.title, "Sample Syllabus")
        self.assertGreaterEqual(len(normalized.sections), 2)
        self.assertIn("Quadratic Expressions", normalized.sections[0].path)
        self.assertTrue(normalized.normalized_text)

    def test_read_docx_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample_notes.docx"
            self._write_docx_fixture(
                docx_path,
                ("Quadratic Expressions", "Expand and factor expressions."),
            )

            text = read_source_text(docx_path)
            read = load_local_source(docx_path, title="Sample Notes", version="2")

        self.assertEqual(text, "Quadratic Expressions\nExpand and factor expressions.")
        self.assertEqual(read.source_document.source_type, "docx")
        self.assertEqual(read.source_document.title, "Sample Notes")
        self.assertEqual(read.raw_text, text)

    def test_read_pdf_fixture_uses_pypdf_fallback(self) -> None:
        class FakePage:
            def __init__(self, text: str) -> None:
                self._text = text

            def extract_text(self) -> str:
                return self._text

        class FakePdfReader:
            def __init__(self, path: str) -> None:
                self.path = path
                self.pages = [FakePage("Introduction"), FakePage("Quadratic expressions")]

        fake_module = ModuleType("PyPDF2")
        fake_module.PdfReader = FakePdfReader

        def import_module_side_effect(module_name: str) -> ModuleType:
            if module_name == "pypdf":
                raise ModuleNotFoundError("pypdf missing")
            if module_name == "PyPDF2":
                return fake_module
            raise ModuleNotFoundError(module_name)

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample_notes.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 local fixture")

            with patch.object(loaders, "import_module", side_effect=import_module_side_effect):
                text = read_source_text(pdf_path)
                read = load_local_source(pdf_path, title="Sample PDF", version="3")

        self.assertEqual(text, "Introduction\nQuadratic expressions")
        self.assertEqual(read.source_document.source_type, "pdf")
        self.assertEqual(read.source_document.title, "Sample PDF")
        self.assertEqual(read.raw_text, text)

    def test_read_pdf_without_reader_support_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "unreadable.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 local fixture")

            def import_module_missing(module_name: str) -> ModuleType:
                raise ModuleNotFoundError(module_name)

            with patch.object(loaders, "import_module", side_effect=import_module_missing), patch.object(
                loaders.shutil, "which", return_value=None
            ):
                with self.assertRaises(UnsupportedSourceFormatError):
                    read_source_text(pdf_path)

    def test_read_pdf_uses_pdftotext_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample_notes.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 local fixture")

            def import_module_missing(module_name: str) -> ModuleType:
                raise ModuleNotFoundError(module_name)

            fake_completed = subprocess.CompletedProcess(
                args=["pdftotext"],
                returncode=0,
                stdout="First page text\nSecond page text\n",
                stderr="",
            )

            with patch.object(loaders, "import_module", side_effect=import_module_missing), patch.object(
                loaders.shutil, "which", return_value="pdftotext"
            ), patch.object(loaders.subprocess, "run", return_value=fake_completed):
                text = read_source_text(pdf_path)

        self.assertEqual(text, "First page text\nSecond page text\n")

    def test_malformed_docx_raises_extraction_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "broken.docx"
            docx_path.write_text("not a zip archive", encoding="utf-8")

            with self.assertRaises(ExtractionError):
                read_source_text(docx_path)

