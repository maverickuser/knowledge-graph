"""AWS DynamoDB repository adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..domain.models import CommunitySummary, DiagnosticRecord, GraphSnapshot
from ..exceptions import StorageBackendUnavailable
from .repository import KnowledgeGraphRepository


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class DynamoDBKnowledgeGraphRepository(KnowledgeGraphRepository):
    """DynamoDB-backed repository for the canonical graph."""

    def __init__(
        self,
        table_name: str,
        region_name: str,
        *,
        snapshot_bucket_name: str | None = None,
        endpoint_url: str | None = None,
        resource: Any | None = None,
        s3_client: Any | None = None,
    ) -> None:
        if resource is None:
            try:
                import boto3
            except Exception as error:  # pragma: no cover - optional backend
                raise StorageBackendUnavailable(
                    "boto3 is required to use the DynamoDB repository"
                ) from error
            resource = boto3.resource("dynamodb", region_name=region_name, endpoint_url=endpoint_url)
            if s3_client is None:
                s3_client = boto3.client("s3", region_name=region_name, endpoint_url=endpoint_url)

        self._table = resource.Table(table_name)
        self._snapshot_bucket_name = snapshot_bucket_name
        self._s3_client = s3_client

    def _put(
        self,
        *,
        artifact_type: str,
        artifact_id: str,
        version: str,
        payload: dict[str, Any],
        graph_version: str | None = None,
        community_id: str | None = None,
        assessment_item_id: str | None = None,
    ) -> None:
        item = {
            "artifact_id": artifact_id,
            "version": version,
            "artifact_type": artifact_type,
            "payload": json.dumps(payload, sort_keys=True),
            "created_at": _utc_now(),
            "artifact_sort_key": f"{artifact_type}#{artifact_id}#{version}",
        }
        if graph_version is not None:
            item["graph_version"] = graph_version
        if community_id is not None:
            item["community_id"] = community_id
        if assessment_item_id is not None:
            item["assessment_item_id"] = assessment_item_id
        self._table.put_item(Item=item)

    def _query_single(self, index_name: str, key_name: str, key_value: str, artifact_type: str | None = None) -> dict[str, Any] | None:
        from boto3.dynamodb.conditions import Attr, Key  # type: ignore

        expression = Key(key_name).eq(key_value)
        query_kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": expression,
        }
        if artifact_type is not None:
            query_kwargs["FilterExpression"] = Attr("artifact_type").eq(artifact_type)
        response = self._table.query(**query_kwargs)
        items = response.get("Items", [])
        if not items:
            return None
        return items[0]

    def _decode(self, payload: dict[str, Any], cls):
        return cls.from_dict(json.loads(payload["payload"]))

    def _snapshot_bucket(self) -> str:
        if not self._snapshot_bucket_name:
            raise StorageBackendUnavailable(
                "snapshot_bucket_name is required to persist graph snapshots with DynamoDB"
            )
        return self._snapshot_bucket_name

    def _snapshot_key(self, snapshot: GraphSnapshot) -> str:
        return f"snapshots/{snapshot.graph_version}/{snapshot.id}.json"

    def _snapshot_counts(self, snapshot: GraphSnapshot) -> dict[str, int]:
        return {
            "source_documents": len(snapshot.source_documents),
            "normalized_documents": len(snapshot.normalized_documents),
            "syllabus_nodes": len(snapshot.syllabus_nodes),
            "concepts": len(snapshot.concepts),
            "skills": len(snapshot.skills),
            "prerequisite_edges": len(snapshot.prerequisite_edges),
            "misconceptions": len(snapshot.misconceptions),
            "evidence_artifacts": len(snapshot.evidence_artifacts),
            "assessment_items": len(snapshot.assessment_items),
            "communities": len(snapshot.communities),
            "community_summaries": len(snapshot.community_summaries),
            "diagnostic_records": len(snapshot.diagnostic_records),
        }

    def _snapshot_metadata(
        self, snapshot: GraphSnapshot, key: str, payload: str
    ) -> dict[str, Any]:
        body = payload.encode("utf-8")
        return {
            "snapshot_id": snapshot.id,
            "graph_version": snapshot.graph_version,
            "version": snapshot.version,
            "seed_bundle_id": snapshot.seed_bundle_id,
            "built_at": snapshot.built_at,
            "s3_bucket": self._snapshot_bucket(),
            "s3_key": key,
            "sha256": sha256(body).hexdigest(),
            "byte_size": len(body),
            "counts": self._snapshot_counts(snapshot),
            "indexes": {
                "graph_version_index": "graph-version-index",
                "community_version_index": "community-version-index",
                "assessment_version_index": "assessment-version-index",
            },
        }

    def save_snapshot(self, snapshot: GraphSnapshot) -> None:
        payload = json.dumps(snapshot.to_dict(), sort_keys=True)
        key = self._snapshot_key(snapshot)
        metadata = self._snapshot_metadata(snapshot, key, payload)
        if self._s3_client is None:
            raise StorageBackendUnavailable(
                "S3 client is required to persist graph snapshots"
            )
        self._s3_client.put_object(
            Bucket=metadata["s3_bucket"],
            Key=metadata["s3_key"],
            Body=payload.encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "graph-version": snapshot.graph_version,
                "snapshot-id": snapshot.id,
                "sha256": metadata["sha256"],
            },
        )
        self._put(
            artifact_type="GraphSnapshotMetadata",
            artifact_id=snapshot.id,
            version=snapshot.version,
            graph_version=snapshot.graph_version,
            payload=metadata,
        )
        for summary in snapshot.community_summaries:
            self.save_summary(summary)
        for diagnostic in snapshot.diagnostic_records:
            self.save_diagnostic_record(diagnostic)

    def load_snapshot(self, graph_version: str) -> GraphSnapshot | None:
        payload = self._query_single(
            "graph-version-index",
            "graph_version",
            graph_version,
            "GraphSnapshotMetadata",
        )
        if payload is None:
            return None
        metadata = json.loads(payload["payload"])
        if self._s3_client is None:
            raise StorageBackendUnavailable("S3 client is required to load graph snapshots")
        response = self._s3_client.get_object(
            Bucket=metadata["s3_bucket"],
            Key=metadata["s3_key"],
        )
        body = response["Body"].read()
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
            body_text = body
        else:
            body_bytes = body
            body_text = body.decode("utf-8")
        checksum = sha256(body_bytes).hexdigest()
        if checksum != metadata["sha256"]:
            raise StorageBackendUnavailable("snapshot checksum mismatch while loading from S3")
        return GraphSnapshot.from_dict(json.loads(body_text))

    def save_summary(self, summary: CommunitySummary) -> None:
        self._put(
            artifact_type="CommunitySummary",
            artifact_id=summary.id,
            version=summary.version,
            graph_version=summary.version,
            community_id=summary.community_id,
            payload=summary.to_dict(),
        )

    def load_summary(self, community_id: str, version: str) -> CommunitySummary | None:
        from boto3.dynamodb.conditions import Attr, Key  # type: ignore

        response = self._table.query(
            IndexName="community-version-index",
            KeyConditionExpression=Key("community_id").eq(community_id) & Key("version").eq(version),
            FilterExpression=Attr("artifact_type").eq("CommunitySummary"),
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._decode(items[0], CommunitySummary)

    def list_summaries(self, graph_version: str | None = None) -> tuple[CommunitySummary, ...]:
        if graph_version is None:
            response = self._table.scan()
        else:
            from boto3.dynamodb.conditions import Attr, Key  # type: ignore

            response = self._table.query(
                IndexName="graph-version-index",
                KeyConditionExpression=Key("graph_version").eq(graph_version),
                FilterExpression=Attr("artifact_type").eq("CommunitySummary"),
            )
        items = response.get("Items", [])
        summaries = [self._decode(item, CommunitySummary) for item in items if item.get("artifact_type") == "CommunitySummary"]
        return tuple(sorted(summaries, key=lambda item: (item.community_id, item.version)))

    def save_diagnostic_record(self, record: DiagnosticRecord) -> None:
        self._put(
            artifact_type="DiagnosticRecord",
            artifact_id=record.id,
            version=record.version,
            graph_version=record.version,
            assessment_item_id=record.assessment_item_id,
            payload=record.to_dict(),
        )

    def load_diagnostic_record(self, record_id: str, version: str) -> DiagnosticRecord | None:
        response = self._table.get_item(Key={"artifact_id": record_id, "version": version})
        item = response.get("Item")
        if not item or item.get("artifact_type") != "DiagnosticRecord":
            return None
        return self._decode(item, DiagnosticRecord)

    def list_diagnostic_records(
        self, assessment_item_id: str, graph_version: str | None = None
    ) -> tuple[DiagnosticRecord, ...]:
        from boto3.dynamodb.conditions import Attr, Key  # type: ignore

        response = self._table.query(
            IndexName="assessment-version-index",
            KeyConditionExpression=Key("assessment_item_id").eq(assessment_item_id),
            FilterExpression=Attr("artifact_type").eq("DiagnosticRecord"),
        )
        items = response.get("Items", [])
        records = [self._decode(item, DiagnosticRecord) for item in items]
        if graph_version is not None:
            records = [record for record in records if record.version == graph_version]
        return tuple(sorted(records, key=lambda item: (item.assessment_item_id, item.version, item.id)))
