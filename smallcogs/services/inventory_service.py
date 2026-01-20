"""
Inventory Service - CRUD operations for inventory data

Handles dataset management, item queries, and data persistence.
"""

from typing import Dict, List, Optional

from smallcogs.models.inventory import Dataset, DatasetSummary, Item, ItemFilter, UploadResult
from smallcogs.services.parser_service import ParserService
from smallcogs.services.stats_service import StatsService


class InventoryService:
    """Main service for inventory CRUD operations."""

    def __init__(self, storage_path: str = "./data"):
        self.storage_path = storage_path
        self.parser = ParserService()
        self.stats_service = StatsService()

        # In-memory storage (replace with database in production)
        self._datasets: Dict[str, Dataset] = {}

    # =========================================================================
    # Dataset CRUD
    # =========================================================================

    def upload_file(
        self,
        file_path: str,
        name: Optional[str] = None,
        skip_rows: int = 0,
    ) -> UploadResult:
        """Upload and parse an inventory file."""
        dataset, warnings = self.parser.parse_file(
            file_path=file_path,
            dataset_name=name,
            skip_rows=skip_rows,
        )

        # Store dataset
        self._datasets[dataset.dataset_id] = dataset

        return UploadResult(
            success=True,
            dataset_id=dataset.dataset_id,
            filename=file_path.split("/")[-1],
            items_count=dataset.items_count,
            records_count=dataset.records_count,
            periods_count=dataset.periods_count,
            date_range_start=dataset.date_range_start,
            date_range_end=dataset.date_range_end,
            categories_found=dataset.categories,
            warnings=warnings,
        )

    def list_datasets(self) -> List[DatasetSummary]:
        """List all datasets."""
        return [
            DatasetSummary(
                dataset_id=ds.dataset_id,
                name=ds.name,
                created_at=ds.created_at,
                items_count=ds.items_count,
                records_count=ds.records_count,
                periods_count=ds.periods_count,
                date_range_start=ds.date_range_start,
                date_range_end=ds.date_range_end,
                categories=ds.categories,
            )
            for ds in self._datasets.values()
        ]

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False

    # =========================================================================
    # Item Queries
    # =========================================================================

    def get_items(
        self,
        dataset_id: str,
        filters: Optional[ItemFilter] = None,
        include_stats: bool = True,
    ) -> List[Dict]:
        """Get items with optional filtering and stats."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return []

        # Get all items
        items = list(dataset.items.values())

        # Apply filters
        if filters:
            items = self._apply_filters(items, dataset, filters)

        # Compute stats if requested
        result = []
        for item in items:
            item_data = item.model_dump()
            if include_stats:
                records = dataset.get_item_records(item.item_id)
                stats = self.stats_service.compute_item_stats(item, records)
                item_data["stats"] = stats.model_dump()
            result.append(item_data)

        return result

    def get_item_detail(self, dataset_id: str, item_id: str) -> Optional[Dict]:
        """Get detailed view of a single item."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None

        detail = self.stats_service.get_item_detail(dataset, item_id)
        if not detail:
            return None

        return detail.model_dump()

    def _apply_filters(
        self,
        items: List[Item],
        dataset: Dataset,
        filters: ItemFilter
    ) -> List[Item]:
        """Apply filters to items list."""
        result = items

        # Text search
        if filters.search:
            search_lower = filters.search.lower()
            result = [i for i in result if search_lower in i.name.lower()]

        # Category filter
        if filters.categories:
            result = [i for i in result if i.category in filters.categories]

        # Vendor filter
        if filters.vendors:
            result = [i for i in result if i.vendor in filters.vendors]

        # On-hand filters (need stats)
        if filters.min_on_hand is not None or filters.max_on_hand is not None:
            filtered = []
            for item in result:
                records = dataset.get_item_records(item.item_id)
                if records:
                    current = records[-1].on_hand
                    if filters.min_on_hand and current < filters.min_on_hand:
                        continue
                    if filters.max_on_hand and current > filters.max_on_hand:
                        continue
                filtered.append(item)
            result = filtered

        return result

    # =========================================================================
    # Analytics
    # =========================================================================

    def get_dashboard_stats(self, dataset_id: str) -> Optional[Dict]:
        """Get dashboard summary statistics."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None

        all_stats = self.stats_service.compute_all_stats(dataset)
        category_summary = self.stats_service.get_category_summary(dataset, all_stats)

        # Compute overall stats
        total_items = len(all_stats)
        total_on_hand = sum(s.current_on_hand for s in all_stats.values())

        # Identify issues
        low_stock = [s for s in all_stats.values() if s.weeks_on_hand and s.weeks_on_hand < 1]
        trending_up = [s for s in all_stats.values() if s.trend_direction.value == "up"]
        trending_down = [s for s in all_stats.values() if s.trend_direction.value == "down"]
        data_issues = [s for s in all_stats.values() if s.has_negative_usage or s.has_gaps]

        return {
            "dataset_id": dataset_id,
            "dataset_name": dataset.name,
            "total_items": total_items,
            "total_on_hand": total_on_hand,
            "periods_count": dataset.periods_count,
            "date_range": {
                "start": str(dataset.date_range_start) if dataset.date_range_start else None,
                "end": str(dataset.date_range_end) if dataset.date_range_end else None,
            },
            "categories": category_summary,
            "alerts": {
                "low_stock_count": len(low_stock),
                "low_stock_items": [s.item_name for s in low_stock[:5]],
                "trending_up_count": len(trending_up),
                "trending_down_count": len(trending_down),
                "data_issues_count": len(data_issues),
            },
        }
