# Google Drive Workflow - TODO

## Completed

- [x] Research Google Drive API capabilities
- [x] Design workflow architecture
- [x] Create GoogleDriveBlock for credentials
- [x] Implement OAuth 2.0 authentication flow
- [x] Implement file listing with pagination
- [x] Implement file download with media API
- [x] Handle Google Workspace file exports (Docs, Sheets, Slides)
- [x] Save file metadata alongside downloads
- [x] Build folder structure hierarchy
- [x] Implement snapshot-based idempotency
- [x] Support incremental backups with date filtering
- [x] Error handling and retry logic
- [x] Backup manifest generation
- [x] Complete documentation

## Testing TODO

- [ ] Test OAuth flow on fresh installation
- [ ] Test with empty Google Drive
- [ ] Test with large files (>1GB)
- [ ] Test with Google Workspace files (Docs, Sheets, Slides)
- [ ] Test incremental backup with modified_after filter
- [ ] Test idempotency (re-run with same snapshot_date)
- [ ] Test error handling (network failures, auth errors)
- [ ] Test rate limiting behavior
- [ ] Verify folder structure accuracy
- [ ] Verify metadata completeness

## Future Enhancements

- [ ] Parallel downloads for improved performance
- [ ] Resume interrupted downloads
- [ ] Deduplication across snapshots (save storage)
- [ ] File hash computation for change detection
- [ ] Selective backup by folder or file type
- [ ] Shared Drive support
- [ ] File version history backup
- [ ] Compression support
- [ ] Progress bar for long operations
- [ ] Email notifications on completion/errors
- [ ] Web UI for browsing backups
- [ ] Restore functionality

## Known Limitations

- Cannot backup Google Sites, My Maps, or other unsupported Google file types
- Sequential downloads (not parallel) may be slow for large drives
- No built-in deduplication across snapshots
- No support for file version history (only latest version)
- Requires manual OAuth authentication on first run
