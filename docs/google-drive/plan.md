# Google Drive Backup Workflow - Plan

## Objective
Create a production-ready backup workflow for Google Drive that downloads files and folders with full metadata preservation, supporting incremental backups and ensuring idempotency.

## Architecture

### API Selection
- **Google Drive API v3** - Full read access to files, folders, and metadata
- **OAuth 2.0** - Standard authentication flow using credentials.json from Google Cloud Console
- **Scopes**: `https://www.googleapis.com/auth/drive.readonly` (read-only access)

### Storage Structure
```
./backups/local/google-drive/
  {user_email}/
    files/
      {snapshot_date}/
        {file_id}.{extension}        # Actual file content
        {file_id}_metadata.json      # File metadata
    folders/
      {snapshot_date}/
        folder_structure.json        # Complete folder hierarchy
    manifests/
      backup_manifest_{snapshot_date}.json  # Backup summary
```

### Idempotency Strategy
1. **Snapshot-based backups**: Each backup is organized by snapshot_date
2. **Deterministic ordering**: Files sorted by (modifiedTime, id) to ensure consistent processing
3. **Skip existing**: Check if snapshot directory and manifest exist before starting
4. **Content-based identification**: Use Google Drive file IDs as unique identifiers
5. **Date filtering**: Support `modified_after` and `modified_before` parameters for incremental backups

## Workflow Components

### Tasks

1. **create_drive_service**
   - Authenticate with OAuth 2.0
   - Load existing token.json or trigger auth flow
   - Return authenticated Drive service

2. **list_all_files**
   - Query Drive API for all accessible files
   - Support date filtering (modifiedTime >= modified_after)
   - Handle pagination with pageToken
   - Sort by modifiedTime, id for deterministic ordering
   - Return list of file metadata dicts

3. **download_file**
   - Download file content using files.get(fileId, alt='media')
   - Handle Google Workspace files (export as PDF/DOCX/etc)
   - Save with original filename and file ID
   - Handle rate limits with exponential backoff

4. **save_file_metadata**
   - Save comprehensive metadata for each file
   - Include: name, mimeType, size, createdTime, modifiedTime, owners, permissions, parents
   - Store in JSON format alongside file

5. **build_folder_structure**
   - Query all folders using mimeType filter
   - Build hierarchical folder tree
   - Save complete structure to JSON

6. **check_snapshot_exists**
   - Check if snapshot directory and manifest exist
   - Return True to skip backup if already complete

7. **save_backup_manifest**
   - Summary statistics: file count, total size, processing duration
   - Snapshot metadata: date, execution time, workflow version
   - Error tracking: failed downloads, skipped files

### Main Flow: backup_google_drive

```python
@flow(name="backup-google-drive")
def backup_google_drive(
    snapshot_date: datetime,
    credentials_block_name: str = "google-drive-credentials",
    modified_after: Optional[datetime] = None,
    max_files: Optional[int] = None,
    include_shared: bool = True,
    output_dir: Path = BACKUP_DIR,
) -> dict:
```

## Data Quality & Validation

1. **Schema validation**: Verify API response structure
2. **Completeness checks**: Ensure all listed files were downloaded
3. **Size verification**: Compare downloaded file size with API metadata
4. **Error tracking**: Log all failed downloads with reasons
5. **Quota monitoring**: Track API quota usage

## Error Handling

1. **API errors**:
   - Rate limits: Exponential backoff with tenacity
   - Auth failures: Clear instructions to re-authenticate
   - Network timeouts: Retry with configurable attempts

2. **Download failures**:
   - Continue on individual file errors
   - Save error details to manifest
   - Create ERROR.json for failed files

3. **Quota limits**:
   - Monitor quota usage via API responses
   - Graceful degradation when limits approached
   - Resume capability using snapshot dates

## Special Considerations

### Google Workspace Files
- Google Docs: Export as DOCX and PDF
- Google Sheets: Export as XLSX and PDF
- Google Slides: Export as PPTX and PDF
- Google Forms: Export as ZIP
- Store both native Google format link and exported files

### Shared Files
- Include files shared with user (if include_shared=True)
- Track ownership in metadata (owned vs shared)
- Handle shared drives separately

### Large Files
- Chunk downloads for files > 100MB
- Resume support using Range headers
- Progress tracking for long operations

## Incremental Backup Strategy

1. **First run**: Download all files (modified_after=None)
2. **Subsequent runs**: Set modified_after to last backup date
3. **Snapshot isolation**: Each backup is self-contained
4. **Diff computation**: Can compare snapshots to identify changes

## Local Execution

### Setup Requirements
1. Python 3.10+
2. Virtual environment with dependencies installed
3. Google Cloud Project with Drive API enabled
4. OAuth 2.0 credentials.json downloaded
5. Environment variable: `GOOGLE_DRIVE_CREDENTIALS_PATH`

### CLI Interface
```bash
# Full backup
python workflows/google_drive.py

# Incremental backup (files modified after date)
python workflows/google_drive.py --modified-after 2024-01-01

# Limit files for testing
python workflows/google_drive.py --max-files 10
```

## Dependencies
- google-api-python-client (already installed)
- google-auth (already installed)
- google-auth-oauthlib (already installed)
- requests (already installed)
- prefect (already installed)
- tenacity (for retry logic - may need to add)

## Testing Plan

1. **Unit tests**:
   - OAuth flow with mock credentials
   - File listing with pagination
   - Download with various MIME types
   - Metadata extraction

2. **Integration tests**:
   - Full backup with test account
   - Incremental backup with date filter
   - Resume from interrupted backup
   - Google Workspace file exports

3. **Edge cases**:
   - Empty Drive
   - Very large files (>1GB)
   - Files with special characters in names
   - Deleted/trashed files
   - Files without download permission

## Monitoring & Observability

1. **Metrics to track**:
   - Files downloaded per run
   - Total bytes downloaded
   - API quota consumed
   - Error rate
   - Processing duration

2. **Logging levels**:
   - INFO: Progress updates (files downloaded, folders processed)
   - WARNING: Skipped files, partial failures
   - ERROR: Critical failures, auth issues
   - DEBUG: API responses, detailed operations

## Future Enhancements

1. **Diff-based incremental backups**: Compare file hashes to detect actual changes
2. **Shared Drive support**: Backup entire shared drives
3. **Version history**: Download previous file versions
4. **Selective backup**: Filter by folder, file type, or size
5. **Compression**: Compress files before storage
6. **Encryption**: Optional encryption at rest
7. **Parallel downloads**: Use async/concurrent downloads for speed
8. **Deduplication**: Avoid storing duplicate files across snapshots

## References
- [Google Drive API v3 Documentation](https://developers.google.com/drive/api/v3/reference)
- [Python Quickstart Guide](https://developers.google.com/drive/api/quickstart/python)
- [File Management Guide](https://developers.google.com/drive/api/guides/manage-downloads)
