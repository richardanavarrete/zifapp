"""
Cache Manager for Beverage Usage Analyzer

Provides file-based caching for processed dataframes to avoid re-parsing
spreadsheets across sessions. Uses Parquet format for efficient storage.
"""

import hashlib
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Cache directory structure
CACHE_DIR = Path(__file__).parent / "data" / "cache"
BEVWEEKLY_CACHE_DIR = CACHE_DIR / "bevweekly"
SALES_MIX_CACHE_DIR = CACHE_DIR / "sales_mix"


def _ensure_cache_dirs():
    """Create cache directories if they don't exist"""
    BEVWEEKLY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SALES_MIX_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_file_hash(uploaded_files: List) -> str:
    """
    Generate a unique hash for uploaded files based on name, size, and content sample.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects

    Returns:
        SHA-256 hash string
    """
    if not uploaded_files:
        return ""

    # Sort files by name for consistent hashing
    files_sorted = sorted(uploaded_files, key=lambda f: f.name)

    hasher = hashlib.sha256()

    for file in files_sorted:
        # Hash filename
        hasher.update(file.name.encode('utf-8'))

        # Hash file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        hasher.update(str(file_size).encode('utf-8'))

        # Hash first 1KB of content (sample)
        file.seek(0)
        content_sample = file.read(1024)
        hasher.update(content_sample)

        # Reset file pointer
        file.seek(0)

    return hasher.hexdigest()


def is_cached(file_hash: str, data_type: str = 'bevweekly') -> bool:
    """
    Check if processed data exists in cache.

    Args:
        file_hash: Hash of the uploaded files
        data_type: Type of data ('bevweekly' or 'sales_mix')

    Returns:
        True if cache exists, False otherwise
    """
    if not file_hash:
        return False

    _ensure_cache_dirs()

    if data_type == 'bevweekly':
        cache_path = BEVWEEKLY_CACHE_DIR / file_hash
        # Check if all required files exist
        required_files = [
            cache_path / "metadata.json",
            cache_path / "summary_df.parquet",
            cache_path / "full_df.parquet",
            cache_path / "features_df.parquet",
            cache_path / "dataset.pkl"
        ]
        return all(f.exists() for f in required_files)

    elif data_type == 'sales_mix':
        cache_path = SALES_MIX_CACHE_DIR / f"{file_hash}.parquet"
        return cache_path.exists()

    return False


def save_to_cache(file_hash: str, data: Dict[str, Any], data_type: str = 'bevweekly'):
    """
    Save processed data to cache.

    Args:
        file_hash: Hash of the uploaded files
        data: Dictionary containing processed dataframes and objects
        data_type: Type of data ('bevweekly' or 'sales_mix')
    """
    if not file_hash:
        return

    _ensure_cache_dirs()

    try:
        if data_type == 'bevweekly':
            cache_path = BEVWEEKLY_CACHE_DIR / file_hash
            cache_path.mkdir(parents=True, exist_ok=True)

            # Save dataframes as parquet
            if 'summary_df' in data and data['summary_df'] is not None:
                data['summary_df'].to_parquet(cache_path / "summary_df.parquet")

            if 'full_df' in data and data['full_df'] is not None:
                data['full_df'].to_parquet(cache_path / "full_df.parquet")

            if 'features_df' in data and data['features_df'] is not None:
                data['features_df'].to_parquet(cache_path / "features_df.parquet")

            # Save dataset object as pickle (contains Item objects and metadata)
            if 'dataset' in data and data['dataset'] is not None:
                with open(cache_path / "dataset.pkl", 'wb') as f:
                    pickle.dump(data['dataset'], f)

            # Save mappings and metadata as JSON
            metadata = {
                'cached_at': datetime.now().isoformat(),
                'vendor_map': data.get('vendor_map', {}),
                'category_map': data.get('category_map', {}),
                'file_hash': file_hash
            }
            with open(cache_path / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)

        elif data_type == 'sales_mix':
            cache_path = SALES_MIX_CACHE_DIR / f"{file_hash}.parquet"
            if 'sales_df' in data and data['sales_df'] is not None:
                data['sales_df'].to_parquet(cache_path)

    except Exception as e:
        # Silently fail cache save - not critical
        print(f"Warning: Failed to save cache: {e}")


def load_from_cache(file_hash: str, data_type: str = 'bevweekly') -> Optional[Dict[str, Any]]:
    """
    Load processed data from cache.

    Args:
        file_hash: Hash of the uploaded files
        data_type: Type of data ('bevweekly' or 'sales_mix')

    Returns:
        Dictionary containing cached data, or None if load fails
    """
    if not file_hash:
        return None

    _ensure_cache_dirs()

    try:
        if data_type == 'bevweekly':
            cache_path = BEVWEEKLY_CACHE_DIR / file_hash

            # Load metadata
            with open(cache_path / "metadata.json", 'r') as f:
                metadata = json.load(f)

            # Load dataframes
            summary_df = pd.read_parquet(cache_path / "summary_df.parquet")
            full_df = pd.read_parquet(cache_path / "full_df.parquet")
            features_df = pd.read_parquet(cache_path / "features_df.parquet")

            # Load dataset object
            with open(cache_path / "dataset.pkl", 'rb') as f:
                dataset = pickle.load(f)

            return {
                'summary_df': summary_df,
                'full_df': full_df,
                'features_df': features_df,
                'dataset': dataset,
                'vendor_map': metadata.get('vendor_map', {}),
                'category_map': metadata.get('category_map', {}),
                'cached_at': metadata.get('cached_at')
            }

        elif data_type == 'sales_mix':
            cache_path = SALES_MIX_CACHE_DIR / f"{file_hash}.parquet"
            sales_df = pd.read_parquet(cache_path)
            return {'sales_df': sales_df}

    except Exception as e:
        # If cache load fails, return None to trigger fresh processing
        print(f"Warning: Failed to load cache: {e}")
        return None


def clear_old_cache(days: int = 7):
    """
    Delete cache files older than specified number of days.

    Args:
        days: Number of days to keep cache files
    """
    _ensure_cache_dirs()

    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0

    for cache_dir in [BEVWEEKLY_CACHE_DIR, SALES_MIX_CACHE_DIR]:
        for item in cache_dir.iterdir():
            try:
                # Check modification time
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < cutoff_date:
                    if item.is_dir():
                        # Remove directory and all contents
                        for subfile in item.rglob('*'):
                            if subfile.is_file():
                                subfile.unlink()
                        item.rmdir()
                    else:
                        item.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Warning: Failed to delete old cache {item}: {e}")

    return deleted_count


def get_cache_info() -> Dict[str, Any]:
    """
    Get information about current cache state.

    Returns:
        Dictionary with cache statistics
    """
    _ensure_cache_dirs()

    bevweekly_count = len(list(BEVWEEKLY_CACHE_DIR.iterdir()))
    sales_mix_count = len(list(SALES_MIX_CACHE_DIR.iterdir()))

    # Calculate total cache size
    total_size = 0
    for cache_dir in [BEVWEEKLY_CACHE_DIR, SALES_MIX_CACHE_DIR]:
        for item in cache_dir.rglob('*'):
            if item.is_file():
                total_size += item.stat().st_size

    # Convert to MB
    total_size_mb = total_size / (1024 * 1024)

    return {
        'bevweekly_cached': bevweekly_count,
        'sales_mix_cached': sales_mix_count,
        'total_size_mb': round(total_size_mb, 2),
        'cache_dir': str(CACHE_DIR)
    }
