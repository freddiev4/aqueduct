# Reddit Workflow - Implementation Plan

## Overview

Build a production-grade workflow to backup Reddit saved posts, comments, and upvoted content using PRAW (Python Reddit API Wrapper).

## Requirements

### Functional Requirements
- [x] Authenticate with Reddit OAuth2 using script app credentials
- [x] Fetch user's saved posts and comments
- [x] Fetch user's comment history
- [x] Fetch user's upvoted content (posts and comments)
- [x] Download media files (images, videos, galleries)
- [x] Save metadata in JSON format
- [x] Support idempotent backups with snapshot dates

### Non-Functional Requirements
- [x] Follow existing workflow patterns (GitHub, YouTube, Amazon)
- [x] Use Prefect for orchestration
- [x] Store all timestamps in UTC timezone
- [x] Implement deterministic ordering (sort by Reddit ID)
- [x] Use download archives for media idempotency
- [x] Handle API rate limits gracefully
- [x] Provide comprehensive error handling and logging

## Architecture

### Authentication
- **Method**: OAuth2 Password Flow (script app)
- **Credentials**: client_id, client_secret, username, password, user_agent
- **Storage**: Prefect Block (RedditBlock)
- **Library**: PRAW 7.7.1+

### Data Sources
1. **Saved Content**: `reddit.user.me().saved()`
   - Returns both submissions and comments
   - Supports pagination via ListingGenerator

2. **Comment History**: `reddit.user.me().comments.new()`
   - Returns user's comments sorted by newest first
   - Supports pagination via ListingGenerator

3. **Upvoted Content**: `reddit.user.me().upvoted()`
   - Returns both upvoted submissions and comments
   - Supports pagination via ListingGenerator

### Storage Structure

```
./backups/local/reddit/
└── {username}/
    ├── saved/
    │   ├── {snapshot_date}/
    │   │   ├── saved.json              # All items in single file
    │   │   ├── {reddit_id}.json        # Individual item files (t3_xxx, t1_xxx)
    │   │   └── media/
    │   │       ├── {reddit_id}.jpg     # Images
    │   │       └── {reddit_id}.mp4     # Videos
    │   ├── backup_manifest_{date}.json
    │   └── download_archive.txt        # Tracks downloaded media
    ├── comments/
    │   └── {snapshot_date}/
    │       ├── comments.json
    │       └── {reddit_id}.json
    └── upvoted/
        └── {snapshot_date}/
            ├── upvoted.json
            ├── {reddit_id}.json
            └── media/
```

### Idempotency Strategy

1. **Snapshot Dates**: Each backup is tied to a specific snapshot date. Re-running with the same date skips existing backups.

2. **Reddit IDs**: Use Reddit's unique IDs for filenames:
   - Submissions: `t3_abc123` (reddit_id: `abc123`)
   - Comments: `t1_def456` (reddit_id: `def456`)

3. **Download Archive**: Track downloaded media in `download_archive.txt` to avoid re-downloading.

4. **Deterministic Sorting**: Sort all API results by Reddit ID before processing.

5. **Existence Checks**: Check if snapshot directory and main JSON file exist before starting backup.

## Implementation Details

### Tasks

1. **create_reddit_session()**
   - Load credentials from RedditBlock
   - Initialize PRAW Reddit instance
   - Verify authentication with `reddit.user.me()`

2. **fetch_saved_posts()**
   - Fetch saved items via `reddit.user.me().saved(limit=None)`
   - Extract data using `extract_item_data()`
   - Sort by Reddit ID for deterministic ordering

3. **fetch_user_comments()**
   - Fetch comments via `reddit.user.me().comments.new(limit=None)`
   - Extract comment data
   - Sort by Reddit ID

4. **fetch_upvoted_content()**
   - Fetch upvoted items via `reddit.user.me().upvoted(limit=None)`
   - Extract data for both submissions and comments
   - Sort by Reddit ID

5. **download_media()**
   - Check download archive for idempotency
   - Download images, videos using requests library
   - Save with Reddit ID as filename
   - Update download archive

6. **save_items_to_disk()**
   - Save all items to single JSON file
   - Create individual per-item JSON files
   - Download media if requested
   - Update download archive

7. **check_snapshot_exists()**
   - Verify snapshot directory and JSON file exist
   - Return True if backup already complete

8. **save_backup_manifest()**
   - Save metadata about the backup run
   - Include item counts, processing duration, snapshot date

### Data Extraction

**Submission Data**:
- reddit_id, fullname (t3_xxx)
- title, author, subreddit
- url, permalink, selftext
- score, num_comments
- created_utc (UTC timezone)
- media_type (image, video, gallery, link)
- media_url (for downloads)

**Comment Data**:
- reddit_id, fullname (t1_xxx)
- body, author, subreddit
- permalink, score
- created_utc (UTC timezone)
- parent_id, parent_type
- submission_id, submission_title

### Media Handling

**Supported Types**:
- **Images**: Direct URLs ending in .jpg, .jpeg, .png, .gif
- **Videos**: Reddit-hosted videos via `submission.media['reddit_video']['fallback_url']`
- **Galleries**: Multiple images via `submission.media_metadata`

**Download Strategy**:
- Use Reddit ID as filename for idempotency
- Check download archive before downloading
- Handle failures gracefully (log error, continue)
- Store in `media/` subdirectory

## Testing Strategy

1. **Unit Tests** (manual verification):
   - Test authentication with valid/invalid credentials
   - Test data extraction for submissions and comments
   - Test media URL parsing

2. **Integration Tests**:
   - Run with `limit=10` to test small backups
   - Verify directory structure
   - Check JSON metadata format
   - Test idempotency (run twice, verify no duplicates)

3. **Edge Cases**:
   - Empty saved/upvoted lists
   - Deleted posts/comments
   - Private/restricted content
   - Media download failures

## Rate Limiting

- Reddit API: ~60 requests/minute for OAuth2
- PRAW automatically handles rate limiting with delays
- ListingGenerator fetches 100 items per API call
- For 1000 items: ~10 API calls = ~1-2 minutes

## Error Handling

1. **Authentication Errors**:
   - Invalid credentials
   - 2FA token required
   - App not configured correctly

2. **API Errors**:
   - Rate limit exceeded (handled by PRAW)
   - Network timeouts
   - Reddit API downtime

3. **Media Download Errors**:
   - Expired URLs
   - Deleted content
   - Network failures

4. **File System Errors**:
   - Disk space
   - Permission issues
   - Path length limits

## Comparison with Existing Workflows

### Similarities (following patterns)
- ✅ Prefect Block for credentials (like GitHub, Amazon)
- ✅ Snapshot date for idempotency (like Amazon, YouTube)
- ✅ Download archive for media (like YouTube)
- ✅ UTC timezone for all timestamps
- ✅ Per-item JSON files + combined file
- ✅ Backup manifest with metadata
- ✅ NO_CACHE policy on fetch tasks

### Differences (Reddit-specific)
- Multiple content types (saved, comments, upvoted)
- Reddit's unique ID scheme (t3_, t1_ prefixes)
- ListingGenerator for pagination (automatic)
- Media extraction varies by type (images, videos, galleries)

## Dependencies

- **praw>=7.7.1**: Reddit API wrapper
- **requests>=2.31.0**: HTTP client for media downloads (already in pyproject.toml)
- **prefect>=3.5.0**: Workflow orchestration (already in pyproject.toml)
- **python-dotenv>=1.2.1**: Environment variable loading (already in pyproject.toml)

## Documentation

1. **Setup Guide** (`docs/reddit/setup.md`):
   - Creating Reddit API app
   - Configuring credentials
   - Running the workflow
   - Backup structure
   - Troubleshooting

2. **Code Documentation**:
   - Comprehensive docstrings
   - Type hints
   - Inline comments for complex logic

## Delivery Checklist

- [x] Implement RedditBlock for credentials
- [x] Implement main workflow in `workflows/reddit.py`
- [x] Add comprehensive docstrings and type hints
- [x] Use UTC timezone for all timestamps
- [x] Implement idempotency (snapshot dates, Reddit IDs, download archive)
- [x] Support all three content types (saved, comments, upvoted)
- [x] Implement media downloads with error handling
- [x] Create deterministic ordering (sort by Reddit ID)
- [x] Write setup documentation
- [x] Include example usage in `__main__` block
- [x] Add to pyproject.toml dependencies (already present)
- [x] Update TODO.md

## Next Steps

1. Test the workflow with a real Reddit account
2. Verify idempotency (run twice, check for duplicates)
3. Test media downloads for different types
4. Create Prefect deployment for scheduled backups
5. Add to CI/CD if applicable
