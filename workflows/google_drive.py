"""
Google Drive Backup Workflow

Downloads all files and folders from Google Drive with metadata preservation. Supports:
- Full backups with optional date filtering
- OAuth2 authentication via Google Cloud Console credentials
- Idempotent backups using snapshot dates
- Metadata preservation for each file
- Google Workspace file exports (Docs, Sheets, Slides)
- Incremental backups using modifiedTime filtering

Requirements:
- google-api-python-client (pip install google-api-python-client)
- google-auth-oauthlib (pip install google-auth-oauthlib)
- google-auth-httplib2 (pip install google-auth-httplib2)
- Valid OAuth2 credentials from Google Cloud Console

Note: Requires OAuth2 credentials.json from Google Cloud Console.
"""

import json
import io
import time
import webbrowser
import wsgiref.simple_server
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger
from prefect.tasks import exponential_backoff

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.google_drive_block import GoogleDriveBlock

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
except ImportError:
    Request = None
    Credentials = None
    Flow = None
    build = None
    MediaIoBaseDownload = None
    HttpError = None


BACKUP_DIR = Path("./backups/local/google-drive")

# Google Drive API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
]

# Workaround for oauthlib being strict about scope changes
import os
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Export formats for Google Workspace files
EXPORT_FORMATS = {
    'application/vnd.google-apps.document': {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pdf': 'application/pdf',
    },
    'application/vnd.google-apps.spreadsheet': {
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pdf': 'application/pdf',
    },
    'application/vnd.google-apps.presentation': {
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'pdf': 'application/pdf',
    },
    'application/vnd.google-apps.drawing': {
        'pdf': 'application/pdf',
        'png': 'image/png',
    },
    'application/vnd.google-apps.form': {
        'zip': 'application/zip',
    },
}


@task(cache_policy=NO_CACHE)
def create_drive_service(credentials_path: str):
    """
    Create and authenticate a Google Drive API service.

    Args:
        credentials_path: Path to the OAuth2 credentials JSON file

    Returns:
        Authenticated Google Drive service object
    """
    logger = get_run_logger()

    if build is None:
        raise ImportError(
            "google-api-python-client is not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        )

    creds = None
    token_path = Path.home() / ".google-drive-tokens" / "token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            logger.info("Starting OAuth2 flow...")
            logger.info("A browser window will open for authorization...")

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
                prompt='consent'
            )

            # Open browser for authorization
            logger.info(f"Opening browser for authorization: {auth_url}")
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

        # Save the credentials for the next run
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
        logger.info(f"Token saved to {token_path}")

    # Build the service
    service = build('drive', 'v3', credentials=creds)
    logger.info("Successfully authenticated with Google Drive API")
    return service


@task(cache_policy=NO_CACHE)
def get_user_info(service) -> str:
    """
    Get the authenticated user's email address.

    Args:
        service: Authenticated Google Drive service

    Returns:
        User's email address
    """
    logger = get_run_logger()
    try:
        about = service.about().get(fields="user").execute()
        email = about.get('user', {}).get('emailAddress', 'user')
        logger.info(f"Authenticated as: {email}")
        return email
    except Exception as e:
        logger.warning(f"Could not get user email: {e}")
        return "user"


@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def list_all_files(
    service,
    modified_after: Optional[datetime] = None,
    include_shared: bool = True,
) -> list[dict]:
    """
    List all files from Google Drive with optional date filtering.

    Args:
        service: Authenticated Google Drive service
        modified_after: Only include files modified after this date
        include_shared: Include files shared with user

    Returns:
        List of file metadata dictionaries, sorted deterministically
    """
    logger = get_run_logger()

    # Build query
    query_parts = []

    # Exclude trashed files
    query_parts.append("trashed = false")

    # Date filtering
    if modified_after:
        # Ensure UTC timezone
        if modified_after.tzinfo is None:
            modified_after = modified_after.replace(tzinfo=timezone.utc)
        elif modified_after.tzinfo != timezone.utc:
            modified_after = modified_after.astimezone(timezone.utc)

        # Format: RFC 3339 timestamp
        date_str = modified_after.isoformat()
        query_parts.append(f"modifiedTime >= '{date_str}'")

    query = " and ".join(query_parts)
    logger.info(f"Listing files with query: {query}")

    all_files = []
    page_token = None

    # Fields to retrieve for each file
    fields = (
        "nextPageToken, files("
        "id, name, mimeType, size, createdTime, modifiedTime, "
        "owners, parents, shared, webViewLink, iconLink, "
        "permissions, trashed, starred, description"
        ")"
    )

    try:
        while True:
            results = service.files().list(
                q=query,
                pageSize=1000,  # Max page size
                fields=fields,
                pageToken=page_token,
                orderBy="modifiedTime,name",  # Deterministic ordering
            ).execute()

            files = results.get('files', [])
            all_files.extend(files)

            logger.info(f"Retrieved {len(files)} files (total: {len(all_files)})")

            page_token = results.get('nextPageToken')
            if not page_token:
                break

    except HttpError as e:
        logger.error(f"Error listing files: {e}")
        raise

    # Sort by (modifiedTime, id) for deterministic ordering
    all_files.sort(key=lambda f: (f.get('modifiedTime', ''), f.get('id', '')))

    logger.info(f"Found {len(all_files)} files total")
    return all_files


@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def download_file(
    service,
    file_metadata: dict,
    output_dir: Path,
) -> dict:
    """
    Download a single file from Google Drive.

    Args:
        service: Authenticated Google Drive service
        file_metadata: File metadata from Drive API
        output_dir: Directory to save the file

    Returns:
        Dictionary with download status and metadata
    """
    logger = get_run_logger()

    file_id = file_metadata['id']
    file_name = file_metadata.get('name', file_id)
    mime_type = file_metadata.get('mimeType', '')

    result = {
        'file_id': file_id,
        'file_name': file_name,
        'mime_type': mime_type,
        'downloaded': False,
        'error': None,
        'exports': [],
    }

    # Check if this is a Google Workspace file that needs export
    is_google_file = mime_type.startswith('application/vnd.google-apps.')

    try:
        if is_google_file:
            # Export Google Workspace files
            if mime_type in EXPORT_FORMATS:
                logger.info(f"Exporting Google Workspace file: {file_name} ({mime_type})")

                for ext, export_mime in EXPORT_FORMATS[mime_type].items():
                    try:
                        # Create filename with extension
                        export_name = f"{file_id}_{file_name}.{ext}"
                        export_path = output_dir / export_name

                        # Export the file
                        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request)

                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                            if status:
                                logger.debug(f"Download {int(status.progress() * 100)}%")

                        # Write to disk
                        with open(export_path, 'wb') as f:
                            f.write(fh.getvalue())

                        result['exports'].append({
                            'format': ext,
                            'mime_type': export_mime,
                            'path': str(export_path),
                            'size': export_path.stat().st_size,
                        })

                        logger.info(f"Exported as {ext}: {export_path}")

                    except HttpError as e:
                        logger.warning(f"Could not export {file_name} as {ext}: {e}")
                        continue

                result['downloaded'] = len(result['exports']) > 0

            else:
                # Google file type we can't export (e.g., Google Maps, Sites)
                logger.warning(f"Cannot export Google file type: {mime_type}")
                result['error'] = f"Unsupported Google file type: {mime_type}"
                result['downloaded'] = False

        else:
            # Regular file - download content
            logger.info(f"Downloading file: {file_name} ({mime_type})")

            # Use file_id in filename to ensure uniqueness
            safe_name = f"{file_id}_{file_name}"
            file_path = output_dir / safe_name

            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download {int(status.progress() * 100)}%")

            # Write to disk
            with open(file_path, 'wb') as f:
                f.write(fh.getvalue())

            result['downloaded'] = True
            result['path'] = str(file_path)
            result['size'] = file_path.stat().st_size

            logger.info(f"Downloaded to: {file_path}")

    except HttpError as e:
        # Safely access HttpError attributes
        status = getattr(e.resp, 'status', 'unknown') if hasattr(e, 'resp') else 'unknown'
        details = getattr(e, 'error_details', str(e))
        error_msg = f"HTTP error {status}: {details}"
        logger.error(f"Failed to download {file_name}: {error_msg}")
        result['error'] = error_msg
    except Exception as e:
        logger.error(f"Failed to download {file_name}: {e}")
        result['error'] = str(e)

    return result


@task(cache_policy=NO_CACHE)
def save_file_metadata(
    file_metadata: dict,
    download_result: dict,
    output_dir: Path,
    snapshot_date: datetime,
) -> Path:
    """
    Save file metadata to JSON.

    Args:
        file_metadata: Original file metadata from Drive API
        download_result: Result from download_file task
        output_dir: Directory to save metadata

    Returns:
        Path to metadata file
    """
    file_id = file_metadata['id']
    metadata_path = output_dir / f"{file_id}_metadata.json"

    # Combine API metadata with download results
    combined_metadata = {
        'file_id': file_id,
        'name': file_metadata.get('name'),
        'mimeType': file_metadata.get('mimeType'),
        'size': file_metadata.get('size'),
        'createdTime': file_metadata.get('createdTime'),
        'modifiedTime': file_metadata.get('modifiedTime'),
        'owners': file_metadata.get('owners', []),
        'parents': file_metadata.get('parents', []),
        'shared': file_metadata.get('shared', False),
        'starred': file_metadata.get('starred', False),
        'description': file_metadata.get('description', ''),
        'webViewLink': file_metadata.get('webViewLink', ''),
        'iconLink': file_metadata.get('iconLink', ''),
        'download_result': download_result,
        'backup_timestamp': snapshot_date.isoformat(),
    }

    with open(metadata_path, 'w') as f:
        json.dump(combined_metadata, f, indent=2, sort_keys=True)

    return metadata_path


@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def build_folder_structure(
    service,
) -> dict:
    """
    Build a hierarchical folder structure from Drive.

    Args:
        service: Authenticated Google Drive service

    Returns:
        Dictionary representing the folder hierarchy
    """
    logger = get_run_logger()

    # Query all folders
    query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"

    folders = []
    page_token = None

    try:
        while True:
            results = service.files().list(
                q=query,
                pageSize=1000,
                fields="nextPageToken, files(id, name, parents, createdTime, modifiedTime)",
                pageToken=page_token,
            ).execute()

            batch = results.get('files', [])
            folders.extend(batch)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

    except HttpError as e:
        logger.error(f"Error listing folders: {e}")
        raise

    logger.info(f"Found {len(folders)} folders")

    # Build folder hierarchy
    folder_map = {}
    for folder in folders:
        folder_map[folder['id']] = {
            'id': folder['id'],
            'name': folder['name'],
            'parents': folder.get('parents', []),
            'createdTime': folder.get('createdTime'),
            'modifiedTime': folder.get('modifiedTime'),
            'children': [],
        }

    # Link children to parents
    root_folders = []
    for folder_id, folder_data in folder_map.items():
        parents = folder_data['parents']
        if not parents:
            # Root folder
            root_folders.append(folder_data)
        else:
            # Add to parent's children
            for parent_id in parents:
                if parent_id in folder_map:
                    folder_map[parent_id]['children'].append(folder_data)

    return {
        'folder_count': len(folders),
        'root_folders': root_folders,
        'folder_map': folder_map,
    }


@task()
def check_snapshot_exists(
    user_email: str,
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
) -> bool:
    """
    Check if a snapshot already exists for the given date.
    Returns True if the snapshot directory and manifest exist.
    """
    logger = get_run_logger()
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    snapshot_dir = output_dir / user_email / "files" / snapshot_str
    manifest_path = output_dir / user_email / "manifests" / f"backup_manifest_{snapshot_str}.json"

    if snapshot_dir.exists() and manifest_path.exists():
        logger.info(f"Snapshot for {snapshot_str} already exists at {snapshot_dir}")
        return True
    return False


@task()
def save_backup_manifest(
    user_email: str,
    snapshot_date: datetime,
    file_count: int,
    downloaded_count: int,
    failed_count: int,
    total_size: int,
    folder_structure: dict,
    workflow_start: float,
    modified_after: Optional[datetime],
    output_dir: Path = BACKUP_DIR,
) -> Path:
    """
    Save a manifest file with backup metadata.

    Args:
        user_email: User's email address
        snapshot_date: Date for this backup snapshot
        file_count: Total number of files found
        downloaded_count: Number of files successfully downloaded
        failed_count: Number of failed downloads
        total_size: Total size in bytes
        folder_structure: Folder hierarchy
        workflow_start: Workflow start timestamp
        modified_after: Optional date filter used
        output_dir: Base backup directory

    Returns:
        Path to manifest file
    """
    logger = get_run_logger()

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    manifest_dir = output_dir / user_email / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"backup_manifest_{snapshot_str}.json"

    manifest = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_version": "1.0.0",
        "python_version": sys.version,
        "user_email": user_email,
        "modified_after": modified_after.isoformat() if modified_after else None,
        "file_count": file_count,
        "downloaded_count": downloaded_count,
        "failed_count": failed_count,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "folder_count": folder_structure.get('folder_count', 0),
        "processing_duration_seconds": time.time() - workflow_start,
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"Saved backup manifest to {manifest_path}")
    return manifest_path


@flow(name="backup-google-drive")
def backup_google_drive(
    snapshot_date: datetime,
    credentials_block_name: str = "google-drive-credentials",
    modified_after: Optional[datetime] = None,
    max_files: Optional[int] = None,
    include_shared: bool = True,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Main flow to backup Google Drive files and folders.

    Args:
        snapshot_date: Date for this backup snapshot (for idempotency)
        credentials_block_name: Name of the Prefect Google Drive credentials block
        modified_after: Only backup files modified after this date (None for all files)
        max_files: Maximum number of files to download (None for all)
        include_shared: Include files shared with user
        output_dir: Base directory for backups

    Returns:
        Dictionary with backup results
    """
    logger = get_run_logger()
    workflow_start = time.time()

    # Ensure snapshot_date is timezone-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    logger.info(f"Starting Google Drive backup (snapshot date: {snapshot_date.isoformat()})")
    if modified_after:
        logger.info(f"Filtering files modified after: {modified_after.isoformat()}")

    # Load credentials
    logger.info(f"Loading Google Drive credentials from block: {credentials_block_name}")
    google_drive_credentials = GoogleDriveBlock.load(credentials_block_name)
    credentials_path = google_drive_credentials.credentials_path

    # Create authenticated service
    service = create_drive_service(credentials_path)

    # Get user info
    user_email = get_user_info(service)

    # Check if snapshot already exists (idempotency)
    if check_snapshot_exists(user_email, snapshot_date, output_dir):
        logger.info(f"Snapshot already exists and is complete. Skipping backup.")
        return {
            "success": True,
            "message": "Snapshot already exists",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Create output directory structure
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    files_dir = output_dir / user_email / "files" / snapshot_str
    folders_dir = output_dir / user_email / "folders" / snapshot_str
    files_dir.mkdir(parents=True, exist_ok=True)
    folders_dir.mkdir(parents=True, exist_ok=True)

    # List all files
    all_files = list_all_files(
        service=service,
        modified_after=modified_after,
        include_shared=include_shared,
    )

    if not all_files:
        logger.warning("No files found")
        return {
            "success": False,
            "message": "No files found",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Limit files if max_files is set
    if max_files:
        logger.info(f"Limiting download to {max_files} files (out of {len(all_files)} total)")
        all_files = all_files[:max_files]

    # Download files and save metadata
    logger.info(f"Downloading {len(all_files)} files...")
    downloaded_count = 0
    failed_count = 0
    total_size = 0

    for i, file_metadata in enumerate(all_files, 1):
        file_name = file_metadata.get('name', 'unknown')
        logger.info(f"Processing file {i}/{len(all_files)}: {file_name}")

        # Download file
        download_result = download_file(
            service=service,
            file_metadata=file_metadata,
            output_dir=files_dir,
        )

        # Save metadata
        save_file_metadata(
            file_metadata=file_metadata,
            download_result=download_result,
            output_dir=files_dir,
            snapshot_date=snapshot_date,
        )

        # Update counters
        if download_result['downloaded']:
            downloaded_count += 1
            if 'size' in download_result:
                total_size += download_result['size']
            # For Google Workspace exports, sum up all export sizes
            for export in download_result.get('exports', []):
                total_size += export.get('size', 0)
        else:
            failed_count += 1

    # Build folder structure
    logger.info("Building folder structure...")
    folder_structure = build_folder_structure(service)

    # Save folder structure
    folder_file = folders_dir / "folder_structure.json"
    with open(folder_file, "w") as f:
        json.dump(folder_structure, f, indent=2, sort_keys=True)
    logger.info(f"Saved folder structure to {folder_file}")

    # Save backup manifest
    manifest_path = save_backup_manifest(
        user_email=user_email,
        snapshot_date=snapshot_date,
        file_count=len(all_files),
        downloaded_count=downloaded_count,
        failed_count=failed_count,
        total_size=total_size,
        folder_structure=folder_structure,
        workflow_start=workflow_start,
        modified_after=modified_after,
        output_dir=output_dir,
    )

    logger.info(f"Successfully backed up {downloaded_count}/{len(all_files)} files")
    if failed_count > 0:
        logger.warning(f"{failed_count} files failed to download")
    logger.info(f"Total size: {total_size / (1024 * 1024):.2f} MB")
    logger.info(f"Manifest saved to {manifest_path}")

    return {
        "success": True,
        "user_email": user_email,
        "file_count": len(all_files),
        "downloaded_count": downloaded_count,
        "failed_count": failed_count,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "folder_count": folder_structure.get('folder_count', 0),
        "manifest_file": str(manifest_path),
        "snapshot_date": snapshot_date.isoformat(),
        "modified_after": modified_after.isoformat() if modified_after else None,
    }


if __name__ == "__main__":
    # Example usage - backup all files
    backup_google_drive(
        snapshot_date=datetime.now(timezone.utc),
        max_files=10,  # Limit to 10 files for testing
    )
