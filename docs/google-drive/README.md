# Google Drive Backup Workflow

A production-ready Prefect workflow for backing up Google Drive files and folders with full metadata preservation.

## Quick Start

```python
from datetime import datetime, timezone
from workflows.google_drive import backup_google_drive

# Full backup
result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
)

# Incremental backup (files modified in last 7 days)
from datetime import timedelta
modified_after = datetime.now(timezone.utc) - timedelta(days=7)

result = backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
    modified_after=modified_after,
)
```

## Features

- **Complete backups**: Downloads all accessible files and folders
- **OAuth 2.0 authentication**: Secure authentication with automatic token refresh
- **Google Workspace exports**: Converts Docs/Sheets/Slides to standard formats
- **Incremental backups**: Only download files modified after a specific date
- **Idempotent**: Safe to re-run with same snapshot date
- **Metadata preservation**: Saves comprehensive metadata for each file
- **Folder structure mapping**: Maintains folder hierarchy information
- **Error resilient**: Continues on individual file failures
- **Rate limit handling**: Automatic retry with exponential backoff

## Setup

See [SETUP.md](./SETUP.md) for detailed setup instructions.

**Quick setup**:
1. Enable Google Drive API in Google Cloud Console
2. Create OAuth 2.0 credentials (Desktop app)
3. Download credentials.json
4. Set environment variable: `GOOGLE_DRIVE_CREDENTIALS_PATH`
5. Register Prefect block
6. Run workflow (will prompt for OAuth authorization)

## Documentation

- [SETUP.md](./SETUP.md) - Detailed setup instructions with screenshots
- [docs.md](./docs.md) - Complete usage documentation and API reference
- [plan.md](./plan.md) - Architecture and design decisions
- [todo.md](./todo.md) - Current status and future enhancements

## Storage Structure

```
./backups/local/google-drive/
  {user_email}/
    files/{snapshot_date}/
      {file_id}_{filename}.ext        # Downloaded files
      {file_id}_metadata.json          # File metadata
    folders/{snapshot_date}/
      folder_structure.json            # Folder hierarchy
    manifests/
      backup_manifest_{snapshot_date}.json  # Backup summary
```

## Google Workspace Files

Google Workspace files are automatically exported to common formats:

| File Type | Exports |
|-----------|---------|
| Google Docs | DOCX, PDF |
| Google Sheets | XLSX, PDF |
| Google Slides | PPTX, PDF |
| Google Drawings | PDF, PNG |
| Google Forms | ZIP |

## Parameters

```python
backup_google_drive(
    snapshot_date: datetime,              # Required: date for this backup
    credentials_block_name: str = "google-drive-credentials",
    modified_after: Optional[datetime] = None,  # Filter files by date
    max_files: Optional[int] = None,      # Limit for testing
    include_shared: bool = True,          # Include shared files
    output_dir: Path = BACKUP_DIR,        # Output directory
)
```

## Idempotency

The workflow is idempotent - running multiple times with the same `snapshot_date` will:
1. Check if snapshot already exists
2. Skip backup if complete
3. Return existing results

This allows safe re-runs and scheduled execution without duplicates.

## Incremental Backups

For regular backups, use `modified_after` to only download changed files:

```python
# Daily backup pattern
from datetime import datetime, timezone, timedelta

yesterday = datetime.now(timezone.utc) - timedelta(days=1)

backup_google_drive(
    snapshot_date=datetime.now(timezone.utc),
    modified_after=yesterday,  # Only files modified since yesterday
)
```

## Best Practices

1. **Test first**: Use `max_files=10` for initial testing
2. **Incremental backups**: Use `modified_after` for regular backups
3. **Full backups monthly**: Run full backup (no filter) once per month
4. **Monitor manifests**: Check `failed_count` for errors
5. **Secure credentials**: Never commit credentials.json or token.json
6. **Verify storage**: Ensure sufficient disk space
7. **Schedule wisely**: Run during off-peak hours for API quota

## Rate Limits

Google Drive API limits:
- 1,000 queries per 100 seconds per user
- 20,000 queries per 100 seconds total

The workflow handles rate limits with:
- Exponential backoff on 429 errors
- Sequential processing to avoid quota exhaustion
- Resumable operations using snapshot dates

## Troubleshooting

### Common Issues

**"redirect_uri_mismatch"**
- Use "Desktop app" type, not "Web application"

**"Access blocked: This app's request is invalid"**
- Configure OAuth consent screen
- Add your email as a test user

**"Could not get user email"**
- Non-critical warning, uses "user" as directory name

**"Cannot export Google file type"**
- Some Google file types can't be exported (Sites, Maps)
- Metadata saved with webViewLink for manual access

See [SETUP.md](./SETUP.md) for more troubleshooting tips.

## Security

- Uses `drive.readonly` scope (read-only access)
- OAuth 2.0 with token refresh
- Credentials stored securely in home directory
- No modification capabilities
- No network access except Google APIs

## Dependencies

All dependencies included in `pyproject.toml`:
- google-api-python-client
- google-auth
- google-auth-oauthlib
- google-auth-httplib2
- prefect
- requests

## Files

- `workflows/google_drive.py` - Main workflow implementation
- `blocks/google_drive_block.py` - Prefect credentials block
- `docs/google-drive/` - Documentation directory
  - `README.md` - This file
  - `SETUP.md` - Setup guide
  - `docs.md` - Complete documentation
  - `plan.md` - Architecture and design
  - `todo.md` - Status and roadmap

## Example Output

```
INFO: Starting Google Drive backup (snapshot date: 2024-01-15T10:30:00+00:00)
INFO: Successfully authenticated with Google Drive API
INFO: Authenticated as: user@example.com
INFO: Listing files with query: trashed = false
INFO: Found 1234 files total
INFO: Downloading 1234 files...
INFO: Processing file 1/1234: Document.pdf
INFO: Downloaded to: ./backups/local/google-drive/user@example.com/files/2024-01-15/abc123_Document.pdf
...
INFO: Building folder structure...
INFO: Found 50 folders
INFO: Saved folder structure to folder_structure.json
INFO: Successfully backed up 1200/1234 files
INFO: 34 files failed to download
INFO: Total size: 5120.0 MB
INFO: Manifest saved to backup_manifest_2024-01-15.json
```

## Contributing

When modifying this workflow:
1. Follow existing workflow patterns (see `workflows/github.py`, `workflows/amazon.py`)
2. Maintain idempotency guarantees
3. Add comprehensive error handling
4. Update documentation
5. Test with various Drive configurations
6. Update TODO.md with changes

## License

Part of the Aqueduct backup system.
