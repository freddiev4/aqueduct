# Aqueduct TODO

This file tracks implementation status and planned work for the Aqueduct backup system.

## Workflows Status

### Implemented ✓
- [x] **GitHub** (`workflows/github.py`) - Repository cloning, commit history
- [x] **YouTube** (`workflows/youtube.py`) - Video downloads via yt-dlp
- [x] **Crunchyroll** (`workflows/crunchyroll.py`) - Anime downloads via multi-downloader-nx
- [x] **Google Photos** (`workflows/google_photos.py`) - Media library backup

### Needs Fixing 🔧
These workflows are in `workflows/to-fix/` and need updates:
- [ ] **Twitter/X** (`workflows/to-fix/twitter.py`) - Tweets, bookmarks, likes with media
- [ ] **Instagram** (`workflows/to-fix/instagram.py`) - User posts and saved posts
- [ ] **Notion** (`workflows/to-fix/notion.py`) - Pages as markdown with media

### Planned 🔄
- [ ] **Google Drive** - File and folder backup
  - Reference: https://developers.google.com/workspace/drive/api/quickstart/python
- [ ] **Amazon Orders** - Order history backup
  - Reference: https://github.com/alexdlaird/amazon-orders
- [ ] **Reddit** - Saved posts, comments, upvoted content
  - Reference: https://praw.readthedocs.io/en/stable/

## Current Work in Progress

### Google Photos Workflow
- [x] Created workflows/google_photos.py with OAuth2 flow
- [x] Created blocks/google_photos_block.py for credentials management
- [x] Added idempotency: snapshot date directories, deterministic sorting
- [x] Created OAuth2 setup documentation (docs/GOOGLE_PHOTOS_SETUP.md)
- [ ] Test with real Google account
- [ ] Add album support (future enhancement)

### Crunchyroll Workflow
- [x] Config-based series management
- [x] Authentication check function
- [x] Season listing helper
- [x] Updated config format with season_id support
- [ ] Test full download flow

### YouTube Workflow
- [x] Idempotent record filenames (date-only format)
- [x] snapshot_date parameter for consistent runs
- [x] Integration with yt-dlp

## Infrastructure

### Completed ✓
- [x] Prefect integration for workflow orchestration
- [x] Local backup structure: `./backups/local/platform/username/content-type/`
- [x] Metadata preservation (JSON files)
- [x] Docker support for Prefect server

### Planned 🔄
- [ ] Remote NAS backup functionality
- [ ] Scheduled deployments (cron-based)
- [ ] Dashboard for backup status monitoring

## Testing Checklist

When testing a workflow:
1. Run with `max_*` parameter set to 1-2 items
2. Verify backup directory structure
3. Check metadata JSON files
4. Run twice to verify idempotency
5. Check logs for error handling
