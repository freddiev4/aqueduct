import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import webbrowser
from urllib.parse import urlparse, parse_qs
import wsgiref.simple_server
import wsgiref.util

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.google_photos_block import GooglePhotosBlock

# Google Photos API scopes
SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.readonly',
    'https://www.googleapis.com/auth/photoslibrary',  # Added broader scope for API access
]

# Workaround for oauthlib being strict about scope changes
import os
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


def get_authenticated_service(credentials_path: str):
    """
    Authenticate with Google Photos API using OAuth2.

    Args:
        credentials_path: Path to the OAuth2 credentials JSON file

    Returns:
        Authenticated Google Photos service object
    """
    creds = None
    token_path = Path.home() / ".google-photos-tokens" / "token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth2 flow...")
            print("A browser window will open for authorization...")

            # Create flow with explicit redirect URI for web applications
            flow = Flow.from_client_secrets_file(
                credentials_path,
                scopes=SCOPES,
                redirect_uri='http://localhost:8080'
            )

            # Get authorization URL with prompt=consent to force re-consent and get refresh_token
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'  # Force consent screen to get refresh_token
            )

            # Open browser for authorization
            print(f"Opening browser for authorization: {auth_url}")
            webbrowser.open(auth_url)

            # Start local server to receive callback
            authorization_code = None

            class CallbackHandler(wsgiref.simple_server.WSGIRequestHandler):
                def log_message(self, format, *args):
                    pass  # Suppress logs

            def wsgi_app(environ, start_response):
                nonlocal authorization_code
                query_string = environ.get('QUERY_STRING', '')
                params = parse_qs(query_string)

                if 'code' in params:
                    authorization_code = params['code'][0]
                    start_response('200 OK', [('Content-Type', 'text/html')])
                    return [b'<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>']
                else:
                    start_response('400 Bad Request', [('Content-Type', 'text/html')])
                    return [b'<html><body><h1>Authentication failed</h1></body></html>']

            server = wsgiref.simple_server.make_server('localhost', 8080, wsgi_app, handler_class=CallbackHandler)
            server.handle_request()

            if authorization_code:
                # Exchange authorization code for credentials
                flow.fetch_token(code=authorization_code)
                creds = flow.credentials
            else:
                raise Exception("Failed to get authorization code")

        # Save the credentials for the next run with all required fields
        with open(token_path, 'w') as token:
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
            }
            # Add optional fields if present
            if hasattr(creds, 'expiry') and creds.expiry:
                token_data['expiry'] = creds.expiry.isoformat()

            json.dump(token_data, token, indent=2)
        print(f"Token saved to {token_path}")

    # Build the service
    service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
    return service


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

    # Get authenticated service
    service = get_authenticated_service(credentials_path)

    # Use a fixed username - getting user info requires additional scopes
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

    # List all media items using the mediaItems.list endpoint
    page_token = None
    while True:
        try:
            # List media items (simpler than search, might have different permissions)
            params = {
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token

            results = service.mediaItems().list(**params).execute()

            media_items = results.get('mediaItems', [])

            for item in media_items:
                # Parse creation time
                creation_time_str = item['mediaMetadata']['creationTime']
                creation_time = datetime.fromisoformat(creation_time_str.replace('Z', '+00:00'))

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
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        except Exception as e:
            print(f"Error fetching media items: {e}")
            break

    # Sort items by creation time and item ID (newest first) for deterministic ordering
    # Using composite key to handle timestamp collisions (e.g., burst mode photos)
    all_items.sort(key=lambda x: (x["creation_time"], x["item"]["id"]), reverse=True)

    # Download items
    for item_data in all_items:
        if max_items and item_count >= max_items:
            break

        item = item_data["item"]
        creation_time = item_data["creation_time"]

        try:
            # Download the media file
            # Get the base URL and append download parameters
            base_url = item['baseUrl']

            # Determine if it's a photo or video
            mime_type = item['mimeType']
            is_video = mime_type.startswith("video/")

            # Get file extension from mime type
            if is_video:
                download_url = f"{base_url}=dv"  # Download video
                extension = mime_type.split("/")[-1]  # e.g., "mp4" from "video/mp4"
            else:
                download_url = f"{base_url}=d"  # Download photo at full resolution
                extension = mime_type.split("/")[-1]  # e.g., "jpeg" from "image/jpeg"

            # Create filename using item ID and extension
            filename = f"{item['id']}.{extension}"
            file_path = backup_path / filename

            # Download the file
            import requests
            response = requests.get(download_url)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)

            # Save metadata for this item
            media_metadata = item['mediaMetadata']
            metadata = {
                "id": item['id'],
                "filename": item.get('filename', filename),
                "creation_time": creation_time.isoformat(),
                "mime_type": mime_type,
                "is_video": is_video,
                "width": media_metadata.get('width'),
                "height": media_metadata.get('height'),
                "description": item.get("description", ""),
                "local_path": str(file_path),
            }

            # Save photo-specific metadata
            if 'photo' in media_metadata:
                photo_metadata = media_metadata['photo']
                metadata["camera_make"] = photo_metadata.get("cameraMake", "")
                metadata["camera_model"] = photo_metadata.get("cameraModel", "")
                metadata["focal_length"] = photo_metadata.get("focalLength", 0.0)
                metadata["aperture_f_number"] = photo_metadata.get("apertureFNumber", 0.0)
                metadata["iso_equivalent"] = photo_metadata.get("isoEquivalent", 0)

            # Save video-specific metadata
            if 'video' in media_metadata:
                video_metadata = media_metadata['video']
                metadata["fps"] = video_metadata.get("fps", 0.0)
                metadata["status"] = video_metadata.get("status", "")

            # Save individual item metadata
            item_metadata_file = backup_path / f"{item['id']}.json"
            with open(item_metadata_file, "w") as f:
                json.dump(metadata, f, indent=2, sort_keys=True)

            downloaded_items.append(metadata)
            item_count += 1
            print(f"Downloaded item {item_count}: {item.get('filename', filename)} ({mime_type})")

        except Exception as e:
            print(f"Error downloading item {item['id']}: {e}")
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
