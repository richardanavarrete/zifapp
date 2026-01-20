"""
API Client for smallCOGS UI

Handles all communication with the backend API.
"""

from typing import Optional, Dict, List, Any
import requests

from ui.config import UIConfig


class APIClient:
    """HTTP client for the smallCOGS API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or UIConfig.API_BASE_URL).rstrip("/")
        self.api_key = api_key or UIConfig.API_KEY
        self.session = requests.Session()

        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key

    # =========================================================================
    # Health
    # =========================================================================

    def health_check(self) -> Dict:
        """Check API health."""
        return self._get("/health")

    # =========================================================================
    # Datasets
    # =========================================================================

    def upload_file(
        self,
        file_path: str,
        name: Optional[str] = None,
        skip_rows: int = 0,
    ) -> Dict:
        """Upload an inventory file."""
        with open(file_path, "rb") as f:
            files = {"file": f}
            params = {"skip_rows": skip_rows}
            if name:
                params["name"] = name
            return self._post("/api/v1/inventory/upload", files=files, params=params)

    def upload_file_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        name: Optional[str] = None,
        skip_rows: int = 0,
    ) -> Dict:
        """Upload file from bytes (for Streamlit file uploader)."""
        files = {"file": (filename, file_bytes)}
        params = {"skip_rows": skip_rows}
        if name:
            params["name"] = name
        return self._post("/api/v1/inventory/upload", files=files, params=params)

    def list_datasets(self) -> List[Dict]:
        """List all datasets."""
        result = self._get("/api/v1/inventory/datasets")
        return result.get("datasets", [])

    def get_dataset(self, dataset_id: str) -> Dict:
        """Get dataset details."""
        return self._get(f"/api/v1/inventory/datasets/{dataset_id}")

    def delete_dataset(self, dataset_id: str) -> Dict:
        """Delete a dataset."""
        return self._delete(f"/api/v1/inventory/datasets/{dataset_id}")

    # =========================================================================
    # Items
    # =========================================================================

    def get_items(
        self,
        dataset_id: str,
        search: Optional[str] = None,
        category: Optional[str] = None,
        include_stats: bool = True,
    ) -> List[Dict]:
        """Get items in a dataset."""
        params = {"include_stats": include_stats}
        if search:
            params["search"] = search
        if category:
            params["category"] = category

        result = self._get(f"/api/v1/inventory/datasets/{dataset_id}/items", params=params)
        return result.get("items", [])

    def get_item_detail(self, dataset_id: str, item_id: str) -> Dict:
        """Get detailed item view."""
        return self._get(f"/api/v1/inventory/datasets/{dataset_id}/items/{item_id}")

    # =========================================================================
    # Analytics
    # =========================================================================

    def get_dashboard(self, dataset_id: str) -> Dict:
        """Get dashboard stats."""
        return self._get(f"/api/v1/inventory/datasets/{dataset_id}/dashboard")

    # =========================================================================
    # HTTP Methods
    # =========================================================================

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        return self._handle_response(resp)

    def _post(
        self,
        path: str,
        json: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=json, files=files, params=params, timeout=60)
        return self._handle_response(resp)

    def _delete(self, path: str) -> Dict:
        url = f"{self.base_url}{path}"
        resp = self.session.delete(url, timeout=30)
        return self._handle_response(resp)

    def _handle_response(self, resp: requests.Response) -> Dict:
        if resp.status_code >= 400:
            try:
                error = resp.json()
            except Exception:
                error = {"error": {"message": resp.text}}
            raise APIError(resp.status_code, error)
        return resp.json()


class APIError(Exception):
    """API error with status code and response."""

    def __init__(self, status_code: int, response: Dict):
        self.status_code = status_code
        self.response = response
        message = response.get("error", {}).get("message", str(response))
        super().__init__(message)
