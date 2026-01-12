# Google Photos Workflow - TODO

## Status: Ready for Testing

### Completed ✓
- [x] Created workflows/google_photos.py with basic structure
- [x] Created blocks/google_photos_block.py for credentials management
- [x] Reviewed existing workflows (instagram.py, github.py) for patterns
- [x] Added google-photos-library-api dependency to pyproject.toml
- [x] Installed dependencies with `uv pip install -e .`
- [x] Updated .env.example with GOOGLE_PHOTOS_CREDENTIALS_PATH
- [x] Reviewed workflow with idempotency-guardian agent
- [x] Fixed critical idempotency issues:
  - [x] Added snapshot date directory structure (YYYY-MM-DD)
  - [x] Implemented idempotency check for existing snapshots
  - [x] Fixed sort key to include item ID for timestamp collisions
  - [x] Added execution_timestamp to metadata
  - [x] Added workflow_version to metadata
- [x] Created OAuth2 setup documentation (docs/GOOGLE_PHOTOS_SETUP.md)

### In Progress 🔄
- [ ] User needs to create OAuth2 credentials from Google Cloud Console
- [ ] User needs to set GOOGLE_PHOTOS_CREDENTIALS_PATH in .env

### Testing 🧪
User can now test the workflow by following these steps:

1. **Set up OAuth2 credentials** (see docs/GOOGLE_PHOTOS_SETUP.md):
   - Create Google Cloud project
   - Enable Photos Library API
   - Configure OAuth consent screen
   - Download credentials.json
   - Set GOOGLE_PHOTOS_CREDENTIALS_PATH in .env

2. **Register the Google Photos block**:
   ```bash
   source .venv/bin/activate
   python blocks/google_photos_block.py
   ```

3. **Test workflow by downloading 1 photo**:
   ```bash
   python workflows/google_photos.py
   ```

4. **Verify backup structure**:
   ```
   backups/local/google_photos/user/media/YYYY-MM-DD/
   ├── <photo-id>.jpg
   ├── <photo-id>.json
   └── media_metadata.json
   ```

5. **Test idempotency**:
   Run the workflow twice with the same snapshot_date and verify:
   - Second run skips download
   - Returns existing metadata
   - No files are modified

### Known Limitations 🚧
- Username defaults to "user" (Google Photos API doesn't expose account username)
- No retry logic for API pagination failures (moderate priority)
- Album support not yet implemented (future enhancement)

### Final Steps 🎯
- [x] Review changes with git diff
- [ ] Commit changes with descriptive message
- [ ] Push to remote: `git push`
- [ ] Output completion promise when testing is successful

## Architecture Notes

### Storage Pattern (S3-style)
```
backups/local/google_photos/{username}/media/{YYYY-MM-DD}/
```

This matches the GitHub workflow pattern and enables:
- Point-in-time snapshots
- Idempotent backups
- Non-destructive updates

### Idempotency Guarantees
The workflow ensures identical results across multiple runs by:
1. Using snapshot_date for temporal filtering
2. Sorting by (creation_time, item_id) for deterministic ordering
3. Checking for existing snapshots before downloading
4. Storing all timestamps in UTC

### Metadata Structure
Each backup includes:
- `media_metadata.json` - Summary with all items, snapshot_date, execution_timestamp, workflow_version
- Individual `<item-id>.json` - Per-photo metadata with EXIF data, dimensions, etc.
