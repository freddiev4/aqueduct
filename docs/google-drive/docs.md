# Google Drive Backup Workflow - Documentation

## Overview

The Google Drive backup workflow downloads all files and folders from Google Drive with full metadata preservation. It supports incremental backups, handles Google Workspace files (Docs, Sheets, Slides) by exporting them to common formats, and ensures idempotent backups using snapshot dates.

## Features

- Full backup of all accessible Google Drive files
- OAuth 2.0 authentication with automatic token refresh
- Google Workspace file exports (Docs → DOCX/PDF, Sheets → XLSX/PDF, etc.)
- Incremental backups using modifiedTime filtering
- Idempotent backups with snapshot dates
- Complete metadata preservation
- Folder structure mapping
- Error tracking and resumable operations
- Rate limit handling with exponential backoff

## Setup

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Name it (e.g., "Aqueduct Drive Backup")
   - Click "Create"
5. Download the credentials:
   - Click the download button next to your new OAuth client
   - Save the file as `credentials.json` in a secure location
   - Note the path to this file

### 2. Environment Setup

Add the credentials path to your environment:

```bash
# Add to .env file
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/your/credentials.json
```

### 3. Register Prefect Block

Create and register the Google Drive credentials block:

```python
from blocks.google_drive_block import GoogleDriveBlock
import os

credentials_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_PATH")
block_name = "google-drive-credentials"

block_id = GoogleDriveBlock(
    credentials_path=credentials_path,
).save(
    block_name,
    overwrite=True,
)

print(f"Google Drive block saved. Name: {block_name}, ID: {block_id}")
```

Or run the block file directly:

```bash
# Edit blocks/google_drive_block.py to uncomment the registration code
python blocks/google_drive_block.py
```

### 4. First Run Authentication

On the first run, the workflow will:
1. Open a browser window for OAuth authentication
2. Ask you to sign in to your Google account
3. Request permission to read your Drive files
4. Save a token to `~/.google-drive-tokens/token.json` for future use

The token will be automatically refreshed when it expires, so you only need to authenticate once.

## Usage

### Basic Usage

Run a full backup:

```python
from datetime import datetime, timezone
from workflows.google_drive import backup_google_drive

result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
)

print(f"Backed up {result['downloaded_count']} files")
print(f"Total size: {result['total_size_mb']} MB")
```

### Incremental Backup

Only backup files modified after a specific date:

```python
from datetime import datetime, timezone, timedelta

# Backup files modified in the last 7 days
modified_after = datetime.now(timezone.utc) - timedelta(days=7)

result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
    modified_after=modified_after,
)
```

### Testing with Limited Files

Test with a small number of files:

```python
result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
    max_files=10,  # Only download 10 files
)
```

### Command Line

Run directly from command line:

```bash
# Full backup
python workflows/google_drive.py

# Edit the __main__ block to customize parameters
```

## Storage Structure

The workflow creates the following directory structure:

```
./backups/local/google-drive/
  {user_email}/
    files/
      {snapshot_date}/
        {file_id}_{filename}.ext        # Actual file content
        {file_id}_{filename}.docx        # Exported Google Doc
        {file_id}_{filename}.pdf         # Exported PDF version
        {file_id}_metadata.json          # File metadata
    folders/
      {snapshot_date}/
        folder_structure.json            # Complete folder hierarchy
    manifests/
      backup_manifest_{snapshot_date}.json  # Backup summary
```

### File Naming

Files are saved with the pattern: `{file_id}_{original_name}.{extension}`

This ensures:
- Uniqueness (Google file IDs are unique)
- Traceability (can link back to Drive using the file ID)
- Readability (original filename is preserved)
- No conflicts (files with same name don't overwrite)

## Google Workspace File Exports

Google Workspace files (Docs, Sheets, Slides, etc.) cannot be downloaded in their native format. The workflow automatically exports them to common formats:

| Google File Type | Export Formats |
|-----------------|----------------|
| Google Docs | DOCX, PDF |
| Google Sheets | XLSX, PDF |
| Google Slides | PPTX, PDF |
| Google Drawings | PDF, PNG |
| Google Forms | ZIP |

Each export is saved as a separate file with the appropriate extension.

## Metadata

Each file's metadata is saved alongside the file in a JSON file with the following information:

- `file_id`: Google Drive file ID
- `name`: Original filename
- `mimeType`: File MIME type
- `size`: File size in bytes
- `createdTime`: When the file was created
- `modifiedTime`: When the file was last modified
- `owners`: List of file owners
- `parents`: Parent folder IDs
- `shared`: Whether the file is shared
- `starred`: Whether the file is starred
- `webViewLink`: Link to view in browser
- `download_result`: Download status and errors

## Idempotency

The workflow ensures idempotency through:

1. **Snapshot dates**: Each backup is organized by date
2. **Pre-flight checks**: Skips backup if snapshot already exists
3. **Deterministic ordering**: Files always processed in the same order (by modifiedTime, id)
4. **Unique identifiers**: Uses Google Drive file IDs for tracking

Re-running the workflow with the same snapshot_date will skip the backup if it already exists.

## Incremental Backups

For regular backups, use the `modified_after` parameter:

```python
# Daily backup - only new/modified files since yesterday
last_backup = datetime(2024, 1, 1, tzinfo=timezone.utc)

result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
    modified_after=last_backup,
)
```

This significantly reduces:
- Download time
- API quota usage
- Storage requirements (each snapshot only contains changed files)

## Folder Structure

The workflow builds a complete hierarchical folder structure saved to `folder_structure.json`:

```json
{
  "folder_count": 50,
  "root_folders": [
    {
      "id": "folder-id-123",
      "name": "My Documents",
      "parents": [],
      "children": [
        {
          "id": "folder-id-456",
          "name": "Work",
          "parents": ["folder-id-123"],
          "children": []
        }
      ]
    }
  ]
}
```

This allows you to:
- Reconstruct the original folder hierarchy
- Find parent folders for any file
- Navigate the folder tree

## Error Handling

The workflow handles various error conditions:

### Authentication Errors
- **Expired token**: Automatically refreshes using refresh_token
- **Invalid credentials**: Prompts for re-authentication
- **Missing credentials file**: Clear error message with setup instructions

### Download Errors
- **File not accessible**: Logs error and continues with next file
- **Rate limit exceeded**: Implements exponential backoff and retry
- **Network errors**: Retries with configurable attempts

### Partial Failures
- Continues downloading remaining files if one fails
- Tracks failed downloads in manifest
- Saves error details in file metadata

## Manifest File

The backup manifest contains summary statistics:

```json
{
  "snapshot_date": "2024-01-15T10:30:00+00:00",
  "execution_timestamp": "2024-01-15T10:35:23+00:00",
  "user_email": "user@example.com",
  "file_count": 1234,
  "downloaded_count": 1200,
  "failed_count": 34,
  "total_size_bytes": 5368709120,
  "total_size_mb": 5120.0,
  "folder_count": 50,
  "processing_duration_seconds": 323.5,
  "modified_after": null
}
```

## API Quota Limits

Google Drive API has the following limits:
- **Queries per 100 seconds per user**: 1,000
- **Queries per 100 seconds**: 20,000

The workflow handles rate limits by:
- Using exponential backoff on 429 errors
- Processing files sequentially to avoid quota exhaustion
- Resuming from where it left off using snapshot dates

For very large drives, consider:
- Running incremental backups more frequently
- Using max_files parameter to split into batches
- Scheduling backups during off-peak hours

## Troubleshooting

### "Could not get user email"
- Non-critical warning
- Workflow will use "user" as the directory name
- Does not affect backup functionality

### "Cannot export Google file type"
- Some Google file types cannot be exported (e.g., Google Sites, My Maps)
- These files are logged with a warning and skipped
- Metadata is still saved with webViewLink for manual access

### "Snapshot already exists"
- Idempotency check passed
- Previous backup with same date already completed
- To force re-run, delete the snapshot directory or use a different date

### Authentication fails with "redirect_uri_mismatch"
- Ensure you created a "Desktop app" OAuth client (not "Web application")
- The redirect URI should be `http://localhost:8080`
- Re-download credentials.json after correcting

## Best Practices

1. **Regular incremental backups**: Run daily with `modified_after` set to yesterday
2. **Monthly full backups**: Run monthly full backup (no `modified_after`) for completeness
3. **Monitor manifest**: Check failed_count and investigate errors
4. **Verify storage**: Ensure sufficient disk space before running
5. **Secure credentials**: Keep credentials.json and token.json secure
6. **Test first**: Use `max_files=10` to test before full backup
7. **Schedule wisely**: Run during off-peak hours to respect API quotas

## Security Notes

- **credentials.json**: Contains OAuth client secrets - DO NOT commit to git
- **token.json**: Contains access/refresh tokens - DO NOT share
- **Read-only scope**: Workflow uses `drive.readonly` scope for safety
- **Local storage**: All files stored locally - ensure disk encryption
- **Shared files**: Workflow can access files shared with you - be mindful of sensitive data

## References

- [Google Drive API v3 Documentation](https://developers.google.com/drive/api/v3/reference)
- [Python Quickstart](https://developers.google.com/drive/api/quickstart/python)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [File Management](https://developers.google.com/drive/api/guides/manage-downloads)
- [Search for Files](https://developers.google.com/drive/api/guides/search-files)
