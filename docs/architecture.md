# Architecture

## Workflow Structure

All backup workflows follow a consistent pattern:

1. **Task-based design**: Each workflow is composed of Prefect `@task` decorated functions for granular operations (authentication, API calls, file downloads, data processing)
2. **Flow orchestration**: A main `@flow` decorated function coordinates tasks and manages the overall backup process
3. **Local-first**: All backups are stored in `./backups/local/` with a hierarchical structure: `platform/username/content-type/`
4. **Metadata preservation**: Each workflow saves both the original content and structured metadata (JSON) for future querying

## Workflow Files

**Working workflows:**
- `workflows/github.py` - Clones repositories and extracts commit history using GitHub GraphQL API
- `workflows/twitter.py` - Downloads tweets, bookmarks, and likes with media files using the X API v2 (xdk SDK)
- `workflows/youtube.py` - Downloads videos via yt-dlp
- `workflows/crunchyroll.py` - Downloads anime via multi-downloader-nx
- `workflows/reddit.py` - Downloads saved posts, comments, and upvoted content using PRAW
- `workflows/google_drive.py` - Downloads files and folders with Google Workspace exports using Drive API
- `workflows/amazon.py` - Downloads order history (requires Python 3.12 or 3.11)
- `workflows/example.py` - Template showing basic Prefect flow structure

**Cannot be automated** (in `workflows/cannot-automate/`):
- `workflows/cannot-automate/google_photos.py` - Google deprecated Library API scopes on April 1, 2025. See README in that directory.

**Workflows needing fixes** (in `workflows/to-fix/`):
- `workflows/to-fix/instagram.py` - Downloads user posts and saved posts
- `workflows/to-fix/notion.py` - Exports pages as markdown with embedded media

## Key Patterns

**Credentials Management**: Workflows expect credentials to be:
- Loaded from Prefect Blocks (e.g., `GitHubCredentials.load("github-freddiev4")`)
- Passed as parameters to the main flow function
- Stored in `.env` file (structure defined in `.env.example`, though currently empty)

**Caching**: Most tasks use `cache_policy=NO_CACHE` to ensure fresh data on each run, avoiding stale backups

**Error Handling**: Workflows implement:
- Retry logic for transient API errors (see `get_all_repositories()` in github.py)
- Graceful degradation (continue on individual item failures)
- Detailed logging to stdout

**Date Filtering**: GitHub workflow supports `until_date` parameter to enable incremental backups (only fetch data up to a specific date)

## Important Notes

- **No Remote Backup Yet**: Remote NAS backup functionality is commented out in workflows (see `backup_to_remote_filesystem()` in github.py)
- **API Rate Limits**: All workflows use `wait_on_rate_limit=True` or implement retry logic for rate limiting
- **Large Datasets**: Workflows support `max_*` parameters to limit download size during development/testing
- **Authentication**: Most workflows support multiple auth methods (OAuth tokens, API keys, session files) to handle different platform requirements
