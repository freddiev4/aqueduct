import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google_photos_library_api import GooglePhotosLibraryApi
from google_photos_library_api.model import MediaItem

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.google_photos_block import GooglePhotosBlock


@task(cache_policy=NO_CACHE)
def download_media_items(
    google_photos_credentials: GooglePhotosBlock,
    snapshot_date: datetime,
    local_backup_dir: Path = Path("./backups/local"),
    max_items: Optional[int] = None,
) -> dict:
    """
    Download all media items from Google Photos up to a snapshot date.

    Args:
        google_photos_credentials: GooglePhotosBlock containing credentials
        snapshot_date: Only download media created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_items: Maximum number of items to download (None for all)

    Returns:
        Dictionary with download statistics
    """
    credentials_path = google_photos_credentials.credentials_path

    # Initialize the API client
    api = GooglePhotosLibraryApi.from_credentials(credentials_path)

    # Get user profile to extract email/username
    # The API doesn't provide a direct way to get username, so we'll use "user" as default
    username = "user"

    # Create backup directory structure with snapshot date segmentation
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    backup_path = local_backup_dir / "google_photos" / username / "media" / snapshot_str

    # Check if snapshot already exists (idempotency)
    metadata_file = backup_path / "media_metadata.json"
    if backup_path.exists() and metadata_file.exists():
        print(f"Snapshot for {snapshot_date.isoformat()} already exists, skipping download...")
        with open(metadata_file, "r") as f:
            existing_metadata = json.load(f)
        return {
            "username": username,
            "item_count": existing_metadata.get("total_items_downloaded", 0),
            "backup_path": str(backup_path),
            "items": existing_metadata.get("items", []),
            "skipped": True,
        }

    backup_path.mkdir(parents=True, exist_ok=True)

    # Download media items
    item_count = 0
    downloaded_items = []

    print(f"Starting download of media items (snapshot date: {snapshot_date.isoformat()})...")

    # Collect all media items and sort deterministically
    all_items = []

    # List all media items
    # The API returns items in reverse chronological order by default
    page_token = None
    while True:
        # Get a page of media items
        media_items = api.media_items.list(page_size=100, page_token=page_token)

        for item in media_items.media_items:
            # Parse creation time
            creation_time_str = item.media_metadata.creation_time
            creation_time = datetime.fromisoformat(creation_time_str.replace("Z", "+00:00"))

            # Ensure UTC timezone
            if creation_time.tzinfo is None:
                creation_time = creation_time.replace(tzinfo=timezone.utc)
            elif creation_time.tzinfo != timezone.utc:
                creation_time = creation_time.astimezone(timezone.utc)

            # Apply temporal filtering - only include items up to snapshot_date
            if creation_time > snapshot_date:
                continue

            all_items.append({
                "item": item,
                "creation_time": creation_time,
            })

        # Check if there are more pages
        page_token = media_items.next_page_token
        if not page_token:
            break

    # Sort items by creation time and item ID (newest first) for deterministic ordering
    # Using composite key to handle timestamp collisions (e.g., burst mode photos)
    all_items.sort(key=lambda x: (x["creation_time"], x["item"].id), reverse=True)

    # Download items
    for item_data in all_items:
        if max_items and item_count >= max_items:
            break

        item = item_data["item"]
        creation_time = item_data["creation_time"]

        try:
            # Download the media file
            # Get the base URL and append download parameters
            base_url = item.base_url

            # Determine if it's a photo or video
            mime_type = item.mime_type
            is_video = mime_type.startswith("video/")

            # Get file extension from mime type
            if is_video:
                download_url = f"{base_url}=dv"  # Download video
                extension = mime_type.split("/")[-1]  # e.g., "mp4" from "video/mp4"
            else:
                download_url = f"{base_url}=d"  # Download photo at full resolution
                extension = mime_type.split("/")[-1]  # e.g., "jpeg" from "image/jpeg"

            # Create filename using item ID and extension
            filename = f"{item.id}.{extension}"
            file_path = backup_path / filename

            # Download the file
            import requests
            response = requests.get(download_url)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)

            # Save metadata for this item
            metadata = {
                "id": item.id,
                "filename": item.filename,
                "creation_time": creation_time.isoformat(),
                "mime_type": mime_type,
                "is_video": is_video,
                "width": item.media_metadata.width,
                "height": item.media_metadata.height,
                "description": getattr(item, "description", ""),
                "local_path": str(file_path),
            }

            # Save photo-specific metadata
            if hasattr(item.media_metadata, "photo") and item.media_metadata.photo:
                photo_metadata = item.media_metadata.photo
                metadata["camera_make"] = getattr(photo_metadata, "camera_make", "")
                metadata["camera_model"] = getattr(photo_metadata, "camera_model", "")
                metadata["focal_length"] = getattr(photo_metadata, "focal_length", 0.0)
                metadata["aperture_f_number"] = getattr(photo_metadata, "aperture_f_number", 0.0)
                metadata["iso_equivalent"] = getattr(photo_metadata, "iso_equivalent", 0)

            # Save video-specific metadata
            if hasattr(item.media_metadata, "video") and item.media_metadata.video:
                video_metadata = item.media_metadata.video
                metadata["fps"] = getattr(video_metadata, "fps", 0.0)
                metadata["status"] = getattr(video_metadata, "status", "")

            # Save individual item metadata
            item_metadata_file = backup_path / f"{item.id}.json"
            with open(item_metadata_file, "w") as f:
                json.dump(metadata, f, indent=2, sort_keys=True)

            downloaded_items.append(metadata)
            item_count += 1
            print(f"Downloaded item {item_count}: {item.filename} ({mime_type})")

        except Exception as e:
            print(f"Error downloading item {item.id}: {e}")
            continue

    # Save summary metadata
    summary_file = backup_path / "media_metadata.json"
    with open(summary_file, "w") as f:
        json.dump({
            "username": username,
            "total_items_downloaded": item_count,
            "snapshot_date": snapshot_date.isoformat(),
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "workflow_version": "1.0.0",
            "items": downloaded_items,
        }, f, indent=2, sort_keys=True)

    print(f"Downloaded {item_count} media items to {backup_path}")

    return {
        "username": username,
        "item_count": item_count,
        "backup_path": str(backup_path),
        "items": downloaded_items,
    }


@flow()
def backup_google_photos(
    google_photos_credentials: Optional[GooglePhotosBlock] = None,
    block_name: str = "google-photos-credentials",
    snapshot_date: Optional[datetime] = None,
    max_items: Optional[int] = None,
    local_backup_dir: Path = Path("./backups/local"),
):
    """
    Main flow to backup Google Photos media items up to a snapshot date.

    Args:
        google_photos_credentials: GooglePhotosBlock containing credentials (if None, will load from block_name)
        block_name: Name of the GooglePhotosBlock to load if google_photos_credentials is not provided
        snapshot_date: Only download media created before or on this date (UTC). Defaults to current time.
        max_items: Maximum number of items to download (None for all)
        local_backup_dir: Base directory for backups
    """
    # Load credentials from block if not provided
    if google_photos_credentials is None:
        google_photos_credentials = GooglePhotosBlock.load(block_name)

    # Default to current UTC time if no snapshot_date provided
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc)
    # Ensure snapshot_date is timezone-aware UTC
    elif snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)
    elif snapshot_date.tzinfo != timezone.utc:
        snapshot_date = snapshot_date.astimezone(timezone.utc)

    print(f"Backing up Google Photos...")
    result = download_media_items(
        google_photos_credentials=google_photos_credentials,
        snapshot_date=snapshot_date,
        local_backup_dir=local_backup_dir,
        max_items=max_items,
    )

    print(f"Google Photos backup completed")
    print(f"  - Media items downloaded: {result.get('item_count', 0)}")

    return result


if __name__ == "__main__":
    # Example usage - download 1 photo for testing
    backup_google_photos(
        block_name="google-photos-credentials",
        max_items=1,  # Download only 1 item for testing
    )
