"""
Supabase Repository

PostgreSQL database operations via Supabase.
All queries are scoped by org_id for multi-tenancy.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from api.supabase.client import get_supabase_client
from houndcogs.models.inventory import DatasetSummary, InventoryDataset, Item, WeeklyRecord
from houndcogs.models.orders import AgentRun, AgentRunSummary, OrderConstraints, OrderTargets, Recommendation

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """
    Supabase PostgreSQL repository.

    All operations are scoped by org_id for multi-tenancy.
    """

    def __init__(self, org_id: UUID):
        """
        Initialize repository with organization context.

        Args:
            org_id: Organization ID for multi-tenant data scoping
        """
        self.org_id = org_id
        self.client = get_supabase_client()

    # =========================================================================
    # Dataset Operations
    # =========================================================================

    def save_dataset(self, dataset: InventoryDataset) -> None:
        """Save an inventory dataset to the database."""
        now = datetime.utcnow().isoformat()

        # Upsert dataset
        dataset_data = {
            "dataset_id": dataset.dataset_id,
            "org_id": str(self.org_id),
            "name": dataset.name,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else now,
            "updated_at": now,
            "source_files": json.dumps(dataset.source_files) if dataset.source_files else "[]",
            "date_range_start": dataset.date_range_start.isoformat() if dataset.date_range_start else None,
            "date_range_end": dataset.date_range_end.isoformat() if dataset.date_range_end else None,
            "items_count": dataset.items_count,
            "weeks_count": getattr(dataset, "weeks_count", len(set(r.week_date for r in dataset.records if hasattr(r, "week_date")))),
            "metadata": "{}",
        }

        self.client.table("datasets").upsert(dataset_data, on_conflict="dataset_id").execute()

        # Insert items (batch)
        if dataset.items:
            items_data = []
            for item_id, item in dataset.items.items():
                items_data.append({
                    "item_id": item_id,
                    "dataset_id": dataset.dataset_id,
                    "org_id": str(self.org_id),
                    "display_name": getattr(item, "display_name", item.name if hasattr(item, "name") else item_id),
                    "category": item.category.value if hasattr(item.category, "value") else str(item.category) if item.category else None,
                    "vendor": item.vendor.value if hasattr(item.vendor, "value") else str(item.vendor) if item.vendor else None,
                    "location": getattr(item, "location", None),
                    "unit_cost": item.unit_cost if item.unit_cost else 0,
                    "unit_of_measure": item.unit_of_measure if item.unit_of_measure else "unit",
                    "metadata": "{}",
                })

            # Delete existing items and insert new ones
            self.client.table("items").delete().eq("dataset_id", dataset.dataset_id).eq("org_id", str(self.org_id)).execute()

            # Batch insert in chunks of 500
            for i in range(0, len(items_data), 500):
                chunk = items_data[i:i + 500]
                self.client.table("items").insert(chunk).execute()

        # Insert records (batch)
        if dataset.records:
            records_data = []
            for record in dataset.records:
                week_date = getattr(record, "week_date", None) or getattr(record, "record_date", None)
                records_data.append({
                    "item_id": record.item_id,
                    "dataset_id": dataset.dataset_id,
                    "org_id": str(self.org_id),
                    "week_date": week_date.isoformat() if week_date else None,
                    "on_hand": record.on_hand,
                    "usage": record.usage if record.usage is not None else 0,
                    "week_name": getattr(record, "week_name", getattr(record, "period_name", None)),
                    "source_file": getattr(record, "source_file", None),
                })

            # Delete existing records and insert new ones
            self.client.table("weekly_records").delete().eq("dataset_id", dataset.dataset_id).eq("org_id", str(self.org_id)).execute()

            # Batch insert in chunks of 1000
            for i in range(0, len(records_data), 1000):
                chunk = records_data[i:i + 1000]
                self.client.table("weekly_records").insert(chunk).execute()

        logger.info(f"Saved dataset {dataset.dataset_id} for org {self.org_id}")

    def get_dataset(self, dataset_id: str) -> Optional[InventoryDataset]:
        """Load a dataset from the database."""
        # Get dataset metadata
        result = self.client.table("datasets").select("*").eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).single().execute()

        if not result.data:
            return None

        row = result.data

        # Get items
        items_result = self.client.table("items").select("*").eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()

        items = {}
        for item_row in items_result.data or []:
            items[item_row["item_id"]] = Item(
                item_id=item_row["item_id"],
                display_name=item_row["display_name"],
                category=item_row["category"],
                vendor=item_row["vendor"],
                location=item_row["location"],
                unit_cost=item_row["unit_cost"],
                unit_of_measure=item_row["unit_of_measure"],
            )

        # Get records
        records_result = self.client.table("weekly_records").select("*").eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).order("week_date").execute()

        records = []
        for rec_row in records_result.data or []:
            records.append(WeeklyRecord(
                item_id=rec_row["item_id"],
                week_date=rec_row["week_date"],
                on_hand=rec_row["on_hand"],
                usage=rec_row["usage"],
                week_name=rec_row["week_name"],
                source_file=rec_row["source_file"],
            ))

        return InventoryDataset(
            dataset_id=row["dataset_id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            source_files=json.loads(row["source_files"]) if row["source_files"] else [],
            date_range_start=row["date_range_start"],
            date_range_end=row["date_range_end"],
            items_count=row["items_count"],
            weeks_count=row["weeks_count"],
            items=items,
            records=records,
        )

    def list_datasets(self, page: int = 1, page_size: int = 50) -> List[DatasetSummary]:
        """List all datasets for the organization."""
        offset = (page - 1) * page_size

        result = self.client.table("datasets").select("*").eq("org_id", str(self.org_id)).order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

        results = []
        for row in result.data or []:
            results.append(DatasetSummary(
                dataset_id=row["dataset_id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                items_count=row["items_count"],
                weeks_count=row["weeks_count"],
                date_range_start=row["date_range_start"],
                date_range_end=row["date_range_end"],
                source_files=json.loads(row["source_files"]) if row["source_files"] else [],
            ))

        return results

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and all related data."""
        # Verify ownership
        result = self.client.table("datasets").select("dataset_id").eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).single().execute()

        if not result.data:
            return False

        # Delete in order: records -> items -> agent_recommendations -> agent_runs -> dataset
        self.client.table("weekly_records").delete().eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()
        self.client.table("items").delete().eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()

        # Get related agent runs
        runs_result = self.client.table("agent_runs").select("run_id").eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()
        for run in runs_result.data or []:
            self.client.table("agent_recommendations").delete().eq("run_id", run["run_id"]).execute()

        self.client.table("agent_runs").delete().eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()
        self.client.table("datasets").delete().eq("dataset_id", dataset_id).eq("org_id", str(self.org_id)).execute()

        logger.info(f"Deleted dataset {dataset_id} for org {self.org_id}")
        return True

    # =========================================================================
    # Agent Run Operations
    # =========================================================================

    def save_agent_run(self, run: AgentRun) -> None:
        """Save an agent run to the database."""
        now = datetime.utcnow().isoformat()

        run_data = {
            "run_id": run.run_id,
            "dataset_id": run.dataset_id,
            "org_id": str(self.org_id),
            "created_at": run.created_at.isoformat() if run.created_at else now,
            "targets": run.targets.model_dump_json(),
            "constraints": run.constraints.model_dump_json(),
            "summary": run.summary.model_dump_json(),
            "status": run.status,
        }

        self.client.table("agent_runs").upsert(run_data, on_conflict="run_id").execute()

        # Save recommendations
        if run.recommendations:
            recs_data = []
            for rec in run.recommendations:
                recs_data.append({
                    "run_id": run.run_id,
                    "item_id": rec.item_id,
                    "suggested_order": rec.suggested_order,
                    "reason_code": rec.reason_code.value if hasattr(rec.reason_code, "value") else str(rec.reason_code),
                    "confidence": rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence),
                    "data": rec.model_dump_json(),
                })

            # Delete existing and insert new
            self.client.table("agent_recommendations").delete().eq("run_id", run.run_id).execute()

            for i in range(0, len(recs_data), 500):
                chunk = recs_data[i:i + 500]
                self.client.table("agent_recommendations").insert(chunk).execute()

        logger.info(f"Saved agent run {run.run_id} for org {self.org_id}")

    def get_agent_run(self, run_id: str) -> Optional[AgentRun]:
        """Load an agent run from the database."""
        result = self.client.table("agent_runs").select("*").eq("run_id", run_id).eq("org_id", str(self.org_id)).single().execute()

        if not result.data:
            return None

        row = result.data

        # Load recommendations
        recs_result = self.client.table("agent_recommendations").select("data").eq("run_id", run_id).execute()

        recommendations = []
        for rec_row in recs_result.data or []:
            recommendations.append(Recommendation.model_validate_json(rec_row["data"]))

        return AgentRun(
            run_id=row["run_id"],
            dataset_id=row["dataset_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            targets=OrderTargets.model_validate_json(row["targets"]),
            constraints=OrderConstraints.model_validate_json(row["constraints"]),
            summary=AgentRunSummary.model_validate_json(row["summary"]),
            recommendations=recommendations,
            status=row["status"],
        )

    def list_agent_runs(
        self,
        dataset_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[AgentRun]:
        """List agent runs for the organization."""
        offset = (page - 1) * page_size

        query = self.client.table("agent_runs").select("*").eq("org_id", str(self.org_id))

        if dataset_id:
            query = query.eq("dataset_id", dataset_id)

        result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

        runs = []
        for row in result.data or []:
            runs.append(AgentRun(
                run_id=row["run_id"],
                dataset_id=row["dataset_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                targets=OrderTargets.model_validate_json(row["targets"]),
                constraints=OrderConstraints.model_validate_json(row["constraints"]),
                summary=AgentRunSummary.model_validate_json(row["summary"]),
                recommendations=[],  # Don't load recommendations for list view
                status=row["status"],
            ))

        return runs

    # =========================================================================
    # Voice Session Operations
    # =========================================================================

    def save_voice_session(self, session_data: dict) -> None:
        """Save a voice counting session."""
        session_data["org_id"] = str(self.org_id)
        self.client.table("voice_sessions").upsert(session_data, on_conflict="session_id").execute()

    def get_voice_session(self, session_id: str) -> Optional[dict]:
        """Get a voice session by ID."""
        result = self.client.table("voice_sessions").select("*").eq("session_id", session_id).eq("org_id", str(self.org_id)).single().execute()
        return result.data

    def list_voice_sessions(self, page: int = 1, page_size: int = 20) -> List[dict]:
        """List voice sessions for the organization."""
        offset = (page - 1) * page_size
        result = self.client.table("voice_sessions").select("*").eq("org_id", str(self.org_id)).order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        return result.data or []

    def save_voice_record(self, record_data: dict) -> None:
        """Save a voice count record."""
        record_data["org_id"] = str(self.org_id)
        self.client.table("voice_count_records").insert(record_data).execute()

    def get_voice_records(self, session_id: str) -> List[dict]:
        """Get all records for a voice session."""
        result = self.client.table("voice_count_records").select("*").eq("session_id", session_id).eq("org_id", str(self.org_id)).order("created_at").execute()
        return result.data or []
