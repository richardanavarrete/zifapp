"""
API Client for HoundCOGS Streamlit UI

Provides a clean interface to the FastAPI backend.
"""

import logging
from typing import Optional, Dict, Any, List, BinaryIO
from dataclasses import dataclass

import requests
from requests.exceptions import RequestException, Timeout

from ui.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Wrapper for API responses."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 0


class HoundCOGSClient:
    """
    Client for the HoundCOGS API.

    Usage:
        client = HoundCOGSClient()

        # Upload inventory
        result = client.upload_inventory(file_bytes, filename)

        # Get recommendations
        result = client.get_recommendations(dataset_id)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.api_key = api_key or settings.api_key
        self.timeout = timeout

        self.session = requests.Session()
        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> APIResponse:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"

        # Set default timeout
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                return APIResponse(
                    success=False,
                    error=error_msg,
                    status_code=response.status_code,
                )

            data = response.json() if response.content else {}
            return APIResponse(
                success=True,
                data=data,
                status_code=response.status_code,
            )

        except Timeout:
            return APIResponse(
                success=False,
                error="Request timed out",
                status_code=0,
            )
        except RequestException as e:
            return APIResponse(
                success=False,
                error=f"Request failed: {str(e)}",
                status_code=0,
            )

    # Health endpoints

    def health_check(self) -> APIResponse:
        """Check if the API is healthy."""
        return self._request("GET", "/health")

    def ready_check(self) -> APIResponse:
        """Check if the API is ready (all dependencies available)."""
        return self._request("GET", "/health/ready")

    # Inventory endpoints

    def upload_inventory(
        self,
        file_content: BinaryIO,
        filename: str,
        name: Optional[str] = None,
    ) -> APIResponse:
        """
        Upload an inventory Excel file.

        Args:
            file_content: File-like object with the file content
            filename: Original filename
            name: Optional dataset name

        Returns:
            APIResponse with dataset info
        """
        files = {"file": (filename, file_content)}
        params = {}
        if name:
            params["name"] = name

        return self._request(
            "POST",
            "/api/v1/inventory/upload",
            files=files,
            params=params,
            timeout=get_settings().upload_timeout,
        )

    def list_datasets(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> APIResponse:
        """List all uploaded datasets."""
        return self._request(
            "GET",
            "/api/v1/inventory/datasets",
            params={"page": page, "page_size": page_size},
        )

    def get_dataset(self, dataset_id: str) -> APIResponse:
        """Get a specific dataset."""
        return self._request("GET", f"/api/v1/inventory/datasets/{dataset_id}")

    def delete_dataset(self, dataset_id: str) -> APIResponse:
        """Delete a dataset."""
        return self._request("DELETE", f"/api/v1/inventory/datasets/{dataset_id}")

    def list_items(
        self,
        dataset_id: str,
        category: Optional[str] = None,
        vendor: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> APIResponse:
        """List items in a dataset."""
        params = {
            "dataset_id": dataset_id,
            "page": page,
            "page_size": page_size,
        }
        if category:
            params["category"] = category
        if vendor:
            params["vendor"] = vendor
        if search:
            params["search"] = search

        return self._request("GET", "/api/v1/inventory/items", params=params)

    def analyze_dataset(self, dataset_id: str) -> APIResponse:
        """Run feature analysis on a dataset."""
        return self._request(
            "POST",
            "/api/v1/inventory/analyze",
            params={"dataset_id": dataset_id},
        )

    # Order endpoints

    def get_recommendations(
        self,
        dataset_id: str,
        targets: Optional[Dict] = None,
        constraints: Optional[Dict] = None,
    ) -> APIResponse:
        """
        Generate order recommendations.

        Args:
            dataset_id: Dataset to analyze
            targets: Optional order targets configuration
            constraints: Optional order constraints

        Returns:
            APIResponse with recommendations
        """
        body = {"dataset_id": dataset_id}
        if targets:
            body["targets"] = targets
        if constraints:
            body["constraints"] = constraints

        return self._request("POST", "/api/v1/orders/recommend", json=body)

    def list_runs(
        self,
        dataset_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> APIResponse:
        """List past agent runs."""
        params = {"page": page, "page_size": page_size}
        if dataset_id:
            params["dataset_id"] = dataset_id

        return self._request("GET", "/api/v1/orders/runs", params=params)

    def get_run(self, run_id: str) -> APIResponse:
        """Get a specific agent run."""
        return self._request("GET", f"/api/v1/orders/runs/{run_id}")

    def approve_run(
        self,
        run_id: str,
        approved_items: Optional[Dict[str, int]] = None,
        rejected_items: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> APIResponse:
        """Approve or modify recommendations."""
        body = {"run_id": run_id}
        if approved_items:
            body["approved_items"] = approved_items
        if rejected_items:
            body["rejected_items"] = rejected_items
        if notes:
            body["notes"] = notes

        return self._request("POST", f"/api/v1/orders/runs/{run_id}/approve", json=body)

    def get_targets(self) -> APIResponse:
        """Get current order targets."""
        return self._request("GET", "/api/v1/orders/targets")

    def update_targets(self, targets: Dict) -> APIResponse:
        """Update order targets."""
        return self._request("PUT", "/api/v1/orders/targets", json=targets)

    # COGS endpoints

    def analyze_cogs(
        self,
        dataset_id: str,
        period_start: str,
        period_end: str,
        sales_data: Optional[Dict[str, float]] = None,
    ) -> APIResponse:
        """Run COGS analysis."""
        body = {
            "dataset_id": dataset_id,
            "period_start": period_start,
            "period_end": period_end,
        }
        if sales_data:
            body["sales_data"] = sales_data

        return self._request("POST", "/api/v1/cogs/analyze", json=body)

    def calculate_pour_costs(
        self,
        dataset_id: str,
        category: Optional[str] = None,
    ) -> APIResponse:
        """Calculate pour costs."""
        params = {"dataset_id": dataset_id}
        if category:
            params["category"] = category

        return self._request("POST", "/api/v1/cogs/pour-cost", params=params)

    def analyze_variance(
        self,
        dataset_id: str,
        period_start: str,
        period_end: str,
        sales_mix_file_id: Optional[str] = None,
    ) -> APIResponse:
        """Run variance analysis."""
        body = {
            "dataset_id": dataset_id,
            "period_start": period_start,
            "period_end": period_end,
        }
        if sales_mix_file_id:
            body["sales_mix_file_id"] = sales_mix_file_id

        return self._request("POST", "/api/v1/cogs/variance", json=body)

    def upload_sales_mix(
        self,
        file_content: BinaryIO,
        filename: str,
    ) -> APIResponse:
        """Upload a sales mix CSV file."""
        files = {"file": (filename, file_content)}
        return self._request(
            "POST",
            "/api/v1/cogs/sales-mix/upload",
            files=files,
            timeout=get_settings().upload_timeout,
        )

    # Voice endpoints

    def create_session(
        self,
        session_name: str,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> APIResponse:
        """Create a new voice counting session."""
        body = {"session_name": session_name}
        if location:
            body["location"] = location
        if notes:
            body["notes"] = notes

        return self._request("POST", "/api/v1/voice/sessions", json=body)

    def list_sessions(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> APIResponse:
        """List voice sessions."""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        return self._request("GET", "/api/v1/voice/sessions", params=params)

    def get_session(self, session_id: str) -> APIResponse:
        """Get a voice session."""
        return self._request("GET", f"/api/v1/voice/sessions/{session_id}")

    def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> APIResponse:
        """Update a voice session."""
        body = {}
        if status:
            body["status"] = status
        if notes:
            body["notes"] = notes

        return self._request("PUT", f"/api/v1/voice/sessions/{session_id}", json=body)

    def transcribe_audio(
        self,
        file_content: BinaryIO,
        filename: str,
        language: str = "en",
        remove_silence: bool = True,
    ) -> APIResponse:
        """Transcribe an audio file."""
        files = {"file": (filename, file_content)}
        params = {
            "language": language,
            "remove_silence": str(remove_silence).lower(),
        }

        return self._request(
            "POST",
            "/api/v1/voice/transcribe",
            files=files,
            params=params,
            timeout=120,  # Transcription can take a while
        )

    def match_text(
        self,
        text: str,
        session_id: Optional[str] = None,
        confidence_threshold: float = 0.8,
        max_alternatives: int = 3,
    ) -> APIResponse:
        """Match transcribed text to inventory items."""
        body = {
            "text": text,
            "confidence_threshold": confidence_threshold,
            "max_alternatives": max_alternatives,
        }
        if session_id:
            body["session_id"] = session_id

        return self._request("POST", "/api/v1/voice/match", json=body)

    def add_record(
        self,
        session_id: str,
        raw_text: str,
        quantity: float,
        item_id: Optional[str] = None,
        unit: str = "bottles",
        confirmed: bool = False,
    ) -> APIResponse:
        """Add a count record to a session."""
        body = {
            "raw_text": raw_text,
            "quantity": quantity,
            "unit": unit,
            "confirmed": confirmed,
        }
        if item_id:
            body["item_id"] = item_id

        return self._request(
            "POST",
            f"/api/v1/voice/sessions/{session_id}/records",
            json=body,
        )

    def export_session(
        self,
        session_id: str,
        format: str = "json",
    ) -> APIResponse:
        """Export a voice session."""
        return self._request(
            "GET",
            f"/api/v1/voice/sessions/{session_id}/export",
            params={"format": format},
        )

    # File endpoints

    def download_file(self, file_id: str) -> requests.Response:
        """
        Download a file (returns raw response for streaming).

        Usage:
            response = client.download_file(file_id)
            if response.status_code == 200:
                with open("output.xlsx", "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
        """
        url = f"{self.base_url}/api/v1/files/{file_id}"
        return self.session.get(url, stream=True, timeout=self.timeout)

    def delete_file(self, file_id: str) -> APIResponse:
        """Delete a file."""
        return self._request("DELETE", f"/api/v1/files/{file_id}")


# Singleton client instance
_client: Optional[HoundCOGSClient] = None


def get_client() -> HoundCOGSClient:
    """Get or create the API client singleton."""
    global _client
    if _client is None:
        _client = HoundCOGSClient()
    return _client
