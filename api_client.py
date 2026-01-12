"""
Python Client Library for Inventory Management API

This client provides a simple interface for both humans and agents
to interact with the inventory management API.

Example Usage (Human):
    client = InventoryClient("http://localhost:8000")
    dataset_id = client.upload_files(["week1.xlsx", "week2.xlsx"])
    summary = client.get_summary(dataset_id)
    result = client.run_agent(dataset_id)
    recommendations = client.get_recommendations(result['run_id'])

Example Usage (Agent):
    agent = AgentClient("http://localhost:8000")
    dataset_id = agent.ingest_data(files)
    analysis = agent.analyze_inventory(dataset_id)
    decisions = agent.make_decisions(dataset_id)
    agent.submit_order(decisions['run_id'], approved_items)
"""

import requests
from typing import List, Dict, Optional, Any
import json
from pathlib import Path


class APIClientError(Exception):
    """Custom exception for API client errors."""
    pass


class BaseClient:
    """Base client with common HTTP methods."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize the client.

        Args:
            base_url: API base URL (e.g., "http://localhost:8000")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise APIClientError(f"GET request failed: {e}")

    def _post(self, endpoint: str, data: Optional[Dict] = None, files: Optional[Dict] = None) -> Dict:
        """Make a POST request."""
        url = f"{self.base_url}{endpoint}"
        try:
            if files:
                response = self.session.post(url, files=files, timeout=self.timeout)
            else:
                response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise APIClientError(f"POST request failed: {e}")

    def _delete(self, endpoint: str) -> Dict:
        """Make a DELETE request."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.delete(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise APIClientError(f"DELETE request failed: {e}")

    def health_check(self) -> Dict:
        """Check if API is healthy."""
        return self._get("/health")


class InventoryClient(BaseClient):
    """
    Human-friendly client for inventory management API.

    This client uses intuitive method names and provides
    convenient interfaces for common operations.
    """

    def upload_files(self, file_paths: List[str]) -> str:
        """
        Upload inventory files and get a dataset ID.

        Args:
            file_paths: List of paths to Excel files

        Returns:
            dataset_id: ID of the created dataset
        """
        files = []
        for path in file_paths:
            file_path = Path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            files.append(('files', (file_path.name, open(file_path, 'rb'),
                                   'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')))

        result = self._post("/upload", files=dict(files))
        return result['dataset_id']

    def list_datasets(self) -> List[Dict]:
        """List all available datasets."""
        result = self._get("/datasets")
        return result['datasets']

    def get_dataset_info(self, dataset_id: str) -> Dict:
        """Get information about a dataset."""
        return self._get(f"/datasets/{dataset_id}")

    def delete_dataset(self, dataset_id: str) -> Dict:
        """Delete a dataset."""
        return self._delete(f"/datasets/{dataset_id}")

    def get_summary(self, dataset_id: str, vendor: Optional[str] = None,
                   category: Optional[str] = None) -> List[Dict]:
        """
        Get summary analytics for all items.

        Args:
            dataset_id: Dataset to analyze
            vendor: Optional vendor filter
            category: Optional category filter

        Returns:
            List of item summaries
        """
        params = {}
        if vendor:
            params['vendor'] = vendor
        if category:
            params['category'] = category

        result = self._get(f"/analytics/{dataset_id}/summary", params=params)
        return result['summary']

    def get_item_details(self, dataset_id: str, item_id: str) -> Dict:
        """Get detailed analytics for a specific item."""
        return self._get(f"/analytics/{dataset_id}/items/{item_id}")

    def get_item_chart(self, dataset_id: str, item_id: str) -> Dict:
        """Get time-series data for charting an item."""
        return self._get(f"/analytics/{dataset_id}/chart/{item_id}")

    def get_trends(self, dataset_id: str) -> Dict:
        """Get trend statistics."""
        return self._get(f"/analytics/{dataset_id}/trends")

    def get_vendor_summary(self, dataset_id: str) -> List[Dict]:
        """Get summary by vendor."""
        result = self._get(f"/analytics/{dataset_id}/vendors")
        return result['vendors']

    def get_category_summary(self, dataset_id: str) -> List[Dict]:
        """Get summary by category."""
        result = self._get(f"/analytics/{dataset_id}/categories")
        return result['categories']

    def run_agent(self, dataset_id: str, usage_column: str = 'avg_4wk',
                 smoothing_level: float = 0.3, trend_threshold: float = 0.1,
                 custom_targets: Optional[Dict[str, float]] = None) -> Dict:
        """
        Run the ordering agent.

        Args:
            dataset_id: Dataset to analyze
            usage_column: Which usage average to use
            smoothing_level: Trend smoothing parameter
            trend_threshold: Trend detection threshold
            custom_targets: Optional category target weeks

        Returns:
            Agent run result with run_id and summary
        """
        data = {
            'usage_column': usage_column,
            'smoothing_level': smoothing_level,
            'trend_threshold': trend_threshold,
            'custom_targets': custom_targets
        }
        return self._post(f"/agent/run/{dataset_id}", data=data)

    def get_agent_runs(self, limit: int = 10) -> List[Dict]:
        """Get history of agent runs."""
        result = self._get("/agent/runs", params={'limit': limit})
        return result['runs']

    def get_recommendations(self, run_id: str, vendor: Optional[str] = None,
                           category: Optional[str] = None,
                           items_to_order_only: bool = False) -> List[Dict]:
        """
        Get recommendations from an agent run.

        Args:
            run_id: Agent run ID
            vendor: Optional vendor filter
            category: Optional category filter
            items_to_order_only: Only return items with qty > 0

        Returns:
            List of recommendations
        """
        params = {}
        if vendor:
            params['vendor'] = vendor
        if category:
            params['category'] = category
        if items_to_order_only:
            params['items_to_order_only'] = items_to_order_only

        result = self._get(f"/agent/runs/{run_id}/recommendations", params=params)
        return result['recommendations']

    def download_order(self, run_id: str, vendor: Optional[str] = None,
                      items_to_order_only: bool = True, save_path: str = "order.csv") -> str:
        """
        Download order recommendations as CSV.

        Args:
            run_id: Agent run ID
            vendor: Optional vendor filter
            items_to_order_only: Only include items with qty > 0
            save_path: Where to save the CSV file

        Returns:
            Path to saved file
        """
        params = {'items_to_order_only': items_to_order_only}
        if vendor:
            params['vendor'] = vendor

        url = f"{self.base_url}/agent/runs/{run_id}/export"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            f.write(response.content)

        return save_path

    def save_order_actions(self, run_id: str, actions: List[Dict]) -> Dict:
        """
        Save user actions for an order.

        Args:
            run_id: Agent run ID
            actions: List of actions with item_id, recommended_qty, approved_qty

        Returns:
            Confirmation message
        """
        return self._post(f"/actions?run_id={run_id}", data={'actions': actions})

    def get_preferences(self) -> Dict:
        """Get all user preferences."""
        result = self._get("/preferences")
        return result['preferences']

    def set_preference(self, item_id: str, **kwargs) -> Dict:
        """
        Set preference for an item.

        Args:
            item_id: Item to set preference for
            **kwargs: Preference fields (target_weeks_override, never_order, etc.)

        Returns:
            Confirmation message
        """
        return self._post(f"/preferences/{item_id}", data=kwargs)

    def get_item_history(self, item_id: str, limit: int = 10) -> Dict:
        """Get historical recommendations and actions for an item."""
        return self._get(f"/items/{item_id}/history", params={'limit': limit})


class AgentClient(BaseClient):
    """
    Agent-focused client using terminology from agent perspective.

    This client uses method names that reflect agent actions and
    provides structured interfaces for autonomous operation.
    """

    def ingest_data(self, file_paths: List[str]) -> str:
        """
        Ingest new inventory data.

        Args:
            file_paths: Paths to data files

        Returns:
            dataset_id: ID for tracking this dataset
        """
        files = []
        for path in file_paths:
            file_path = Path(path)
            files.append(('files', (file_path.name, open(file_path, 'rb'),
                                   'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')))

        result = self._post("/upload", files=dict(files))
        return result['dataset_id']

    def analyze_inventory(self, dataset_id: str) -> Dict:
        """
        Analyze inventory state.

        Args:
            dataset_id: Dataset to analyze

        Returns:
            Analysis results with trends, stats, and issues
        """
        summary = self._get(f"/analytics/{dataset_id}/summary")
        trends = self._get(f"/analytics/{dataset_id}/trends")

        return {
            'summary': summary['summary'],
            'trends': trends['stats'],
            'trending_up': trends['trending_up'],
            'trending_down': trends['trending_down'],
            'low_stock': trends['low_stock']
        }

    def make_decisions(self, dataset_id: str, usage_metric: str = 'avg_4wk',
                       policy_params: Optional[Dict] = None) -> Dict:
        """
        Generate ordering decisions.

        Args:
            dataset_id: Dataset to decide on
            usage_metric: Which usage metric to base decisions on
            policy_params: Optional policy configuration

        Returns:
            Decision results with run_id and recommendations
        """
        data = {
            'usage_column': usage_metric,
            'smoothing_level': policy_params.get('smoothing_level', 0.3) if policy_params else 0.3,
            'trend_threshold': policy_params.get('trend_threshold', 0.1) if policy_params else 0.1,
            'custom_targets': policy_params.get('targets') if policy_params else None
        }

        return self._post(f"/agent/run/{dataset_id}", data=data)

    def get_decision_history(self, limit: int = 10) -> List[Dict]:
        """
        Retrieve past decisions.

        Args:
            limit: Number of past runs to retrieve

        Returns:
            List of past decision runs
        """
        result = self._get("/agent/runs", params={'limit': limit})
        return result['runs']

    def get_decision_details(self, run_id: str) -> List[Dict]:
        """
        Get detailed recommendations from a decision run.

        Args:
            run_id: Decision run identifier

        Returns:
            List of item-level recommendations
        """
        result = self._get(f"/agent/runs/{run_id}/recommendations")
        return result['recommendations']

    def submit_order(self, run_id: str, approved_items: List[Dict]) -> Dict:
        """
        Submit approved order.

        Args:
            run_id: Decision run ID
            approved_items: Items approved for ordering

        Returns:
            Submission confirmation
        """
        return self._post(f"/actions?run_id={run_id}", data={'actions': approved_items})

    def learn_from_feedback(self, item_id: str, feedback: Dict) -> Dict:
        """
        Store feedback for future decisions.

        Args:
            item_id: Item the feedback is about
            feedback: Feedback data (preferences, corrections)

        Returns:
            Confirmation
        """
        return self._post(f"/preferences/{item_id}", data=feedback)

    def inspect_item(self, dataset_id: str, item_id: str) -> Dict:
        """
        Deep inspection of a specific item.

        Args:
            dataset_id: Dataset context
            item_id: Item to inspect

        Returns:
            Detailed item analysis
        """
        details = self._get(f"/analytics/{dataset_id}/items/{item_id}")
        history = self._get(f"/items/{item_id}/history")

        return {
            'current_state': details['features'],
            'metadata': details['item'],
            'weekly_history': details['weekly_history'],
            'decision_history': history['recommendations'],
            'action_history': history['actions']
        }

    def get_knowledge_base(self) -> Dict:
        """
        Retrieve learned preferences and patterns.

        Returns:
            Knowledge base with preferences
        """
        result = self._get("/preferences")
        return {'preferences': result['preferences']}


# ============================================================================
# Convenience Functions
# ============================================================================

def create_client(base_url: str = "http://localhost:8000", mode: str = "human") -> BaseClient:
    """
    Create an appropriate client instance.

    Args:
        base_url: API base URL
        mode: "human" for InventoryClient or "agent" for AgentClient

    Returns:
        Configured client instance
    """
    if mode == "human":
        return InventoryClient(base_url)
    elif mode == "agent":
        return AgentClient(base_url)
    else:
        raise ValueError(f"Invalid mode: {mode}. Use 'human' or 'agent'")
