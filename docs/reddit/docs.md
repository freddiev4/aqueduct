# Reddit Workflow - Documentation

## Overview

The Reddit backup workflow archives your personal Reddit content including saved posts, comment history, and upvoted content. It uses the PRAW library (Python Reddit API Wrapper) to access Reddit's OAuth2 API and downloads content with full metadata preservation.

## Architecture

### Components

1. **RedditBlock** (`blocks/reddit_block.py`)
   - Prefect Block for storing Reddit OAuth2 credentials
   - Fields: client_id, client_secret, username, password, user_agent
   - Securely stores credentials using Prefect's SecretStr type

2. **Main Workflow** (`workflows/reddit.py`)
   - Prefect flow: `backup_reddit_content()`
   - Orchestrates fetching, downloading, and saving content
   - Supports three content types: saved, comments, upvoted

### Authentication Flow

```
1. Load RedditBlock credentials
2. Initialize PRAW Reddit instance
3. Authenticate using Password Flow (OAuth2)
4. Verify authentication with reddit.user.me()
5. Fetch content via authenticated API calls
```

### Data Flow

```
Reddit API (PRAW)
    ↓
fetch_saved_posts() / fetch_user_comments() / fetch_upvoted_content()
    ↓
extract_item_data() → extract_submission_data() / extract_comment_data()
    ↓
save_items_to_disk()
    ├── Save combined JSON file
    ├── Save individual item JSON files
    └── download_media() → Download images/videos
        ↓
save_backup_manifest()
```

## Idempotency Implementation

### 1. Snapshot Dates
- Each backup run is tied to a specific snapshot date (UTC)
- Directory structure includes snapshot date: `{username}/{content_type}/{snapshot_date}/`
- Re-running with the same snapshot date skips existing backups

### 2. Reddit ID-Based Filenames
Reddit uses unique identifiers for all content:
- **Submissions** (posts): `t3_abc123` where `abc123` is the reddit_id
- **Comments**: `t1_def456` where `def456` is the reddit_id

All files use the reddit_id for consistent naming:
- JSON files: `{reddit_id}.json` (e.g., `abc123.json`)
- Media files: `{reddit_id}.jpg` (e.g., `abc123.jpg`)

### 3. Download Archive
- Maintains `download_archive.txt` with list of downloaded Reddit IDs
- Checked before downloading media to avoid duplicates
- Shared across snapshot dates to prevent re-downloading

### 4. Deterministic Sorting
- All API results are sorted by Reddit ID before processing
- Ensures consistent ordering across multiple runs
- Example: `['t3_aaa', 't3_bbb', 't3_ccc']` always in same order

### 5. Existence Checks
Before starting a backup:
- Check if snapshot directory exists
- Check if main JSON file exists
- Skip backup if both exist (already complete)

## Content Types

### Saved Posts
**API**: `reddit.user.me().saved(limit=None)`

Returns:
- Saved submissions (posts)
- Saved comments

Data extracted:
- Post metadata (title, author, subreddit, score)
- Comment metadata (body, author, parent context)
- Media URLs for downloads

### Comment History
**API**: `reddit.user.me().comments.new(limit=None)`

Returns:
- All comments by the authenticated user
- Sorted by newest first

Data extracted:
- Comment text, author, subreddit
- Parent context (submission or comment)
- Submission title and ID for context

### Upvoted Content
**API**: `reddit.user.me().upvoted(limit=None)`

Returns:
- Upvoted submissions (posts)
- Upvoted comments

Data extracted:
- Same as saved content
- Includes items you upvoted but didn't save

## Media Handling

### Supported Media Types

1. **Images**
   - Direct image URLs (i.redd.it, i.imgur.com, etc.)
   - Extensions: .jpg, .jpeg, .png, .gif
   - Downloaded as-is

2. **Videos**
   - Reddit-hosted videos
   - Accessed via `submission.media['reddit_video']['fallback_url']`
   - Downloaded as MP4 files

3. **Galleries**
   - Multiple images in a single post
   - Accessed via `submission.media_metadata`
   - Each image downloaded separately (future enhancement)

### Download Strategy

1. Check if item has media (`media_type` field)
2. Check download archive for idempotency
3. Check if file already exists on disk
4. Download media using requests library
5. Save with Reddit ID as filename
6. Update download archive

### Error Handling

Media download failures are non-fatal:
- Log error with Reddit ID and URL
- Continue with remaining downloads
- Return None for failed downloads

## Storage Format

### Directory Structure

```
./backups/local/reddit/
└── {username}/
    ├── saved/
    │   ├── {snapshot_date}/        # e.g., 2026-02-05/
    │   │   ├── saved.json          # All items combined
    │   │   ├── {reddit_id}.json    # Individual items
    │   │   └── media/
    │   │       └── {reddit_id}.jpg
    │   ├── backup_manifest_{date}.json
    │   └── download_archive.txt
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

### JSON Schema

**Combined File** (`saved.json`, `comments.json`, `upvoted.json`):
```json
{
  "snapshot_date": "2026-02-05T00:00:00+00:00",
  "snapshot_date_str": "2026-02-05",
  "backup_timestamp": "2026-02-05T12:34:56+00:00",
  "username": "your_username",
  "content_type": "saved",
  "item_count": 42,
  "items": [
    {
      "reddit_id": "abc123",
      "fullname": "t3_abc123",
      "type": "submission",
      "title": "...",
      ...
    }
  ]
}
```

**Submission Item**:
```json
{
  "reddit_id": "abc123",
  "fullname": "t3_abc123",
  "type": "submission",
  "title": "Interesting post title",
  "author": "post_author",
  "subreddit": "AskReddit",
  "url": "https://i.redd.it/image.jpg",
  "permalink": "https://www.reddit.com/r/AskReddit/comments/abc123/...",
  "selftext": "Post content here...",
  "is_self": false,
  "score": 1234,
  "num_comments": 56,
  "created_utc": "2026-01-15T10:30:00+00:00",
  "over_18": false,
  "spoiler": false,
  "stickied": false,
  "locked": false,
  "domain": "i.redd.it",
  "media_type": "image",
  "media_url": "https://i.redd.it/abc123.jpg"
}
```

**Comment Item**:
```json
{
  "reddit_id": "def456",
  "fullname": "t1_def456",
  "type": "comment",
  "body": "This is my comment text...",
  "author": "your_username",
  "subreddit": "AskReddit",
  "permalink": "https://www.reddit.com/r/AskReddit/comments/abc123/title/def456/",
  "score": 42,
  "created_utc": "2026-01-15T11:00:00+00:00",
  "edited": false,
  "stickied": false,
  "parent_id": "t3_abc123",
  "parent_type": "submission",
  "submission_id": "abc123",
  "submission_title": "Interesting post title"
}
```

**Backup Manifest**:
```json
{
  "snapshot_date": "2026-02-05T00:00:00+00:00",
  "snapshot_date_str": "2026-02-05",
  "execution_timestamp": "2026-02-05T12:34:56+00:00",
  "workflow_version": "1.0.0",
  "python_version": "3.11.7 (main, Jan 15 2024...)",
  "username": "your_username",
  "content_type": "saved",
  "item_count": 42,
  "media_downloaded": 15,
  "processing_duration_seconds": 123.45,
  "already_existed": false,
  "items_file": "/path/to/saved.json"
}
```

## Rate Limits & Performance

### Reddit API Rate Limits
- **OAuth2 authenticated**: ~60 requests per minute
- **PRAW handles rate limiting automatically** with built-in delays
- ListingGenerator fetches 100 items per API call

### Performance Estimates

| Items | API Calls | Time Estimate |
|-------|-----------|---------------|
| 100   | 1-2       | ~5-10 seconds |
| 1,000 | 10        | ~1-2 minutes  |
| 10,000| 100       | ~10-20 minutes|

Note: Media downloads add additional time based on file sizes.

### Optimization Tips

1. **Disable media downloads** for faster testing:
   ```python
   backup_reddit_content(
       snapshot_date=datetime.now(timezone.utc),
       download_media=False,
   )
   ```

2. **Use limit parameter** for testing:
   ```python
   backup_reddit_content(
       snapshot_date=datetime.now(timezone.utc),
       limit=10,  # Only fetch first 10 items
   )
   ```

3. **Backup only specific content types**:
   ```python
   backup_reddit_content(
       snapshot_date=datetime.now(timezone.utc),
       content_types=["saved"],  # Skip comments and upvoted
   )
   ```

## Error Handling

### Authentication Errors
- **Invalid credentials**: Raises exception, workflow fails
- **2FA required**: Append 2FA token to password (`password:123456`)
- **App configuration**: Verify app type is "script"

### API Errors
- **Rate limit exceeded**: PRAW automatically retries with delay
- **Network timeout**: Raises exception after timeout
- **Reddit API downtime**: Raises exception, retry workflow later

### Media Download Errors
- **Expired URL**: Log error, continue with other downloads
- **Deleted content**: Log error, continue
- **Network failure**: Log error, continue

### File System Errors
- **Disk full**: Raises exception, workflow fails
- **Permission denied**: Raises exception, workflow fails
- **Path too long**: Raises exception (rare on modern systems)

## Testing

### Manual Testing Steps

1. **Test authentication**:
   ```python
   from blocks.reddit_block import RedditBlock
   from workflows.reddit import create_reddit_session

   credentials = RedditBlock.load("reddit-credentials")
   reddit = create_reddit_session(credentials)
   print(reddit.user.me())  # Should print username
   ```

2. **Test with limited items**:
   ```python
   backup_reddit_content(
       snapshot_date=datetime.now(timezone.utc),
       limit=5,
       download_media=False,
   )
   ```

3. **Verify directory structure**:
   ```bash
   tree ./backups/local/reddit/
   ```

4. **Test idempotency**:
   ```python
   # Run twice with same snapshot date
   snapshot = datetime.now(timezone.utc)
   backup_reddit_content(snapshot_date=snapshot)
   backup_reddit_content(snapshot_date=snapshot)  # Should skip
   ```

5. **Check logs**:
   - Look for "already exists, skipping" messages
   - Verify item counts
   - Check for errors

## Troubleshooting

### Common Issues

**"invalid_grant" error**
- Solution: Verify username and password are correct
- For 2FA: Append token to password: `password:123456`

**"No saved items found"**
- Solution: Check if you have saved content on Reddit
- Try with different content type (comments, upvoted)

**Media download failures**
- Solution: Check Reddit URL in browser
- Some media may be deleted or expired
- Workflow continues with other downloads

**"Snapshot already exists"**
- Solution: This is expected (idempotency working)
- Use different snapshot date for new backup
- Or delete existing snapshot directory

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

backup_reddit_content(snapshot_date=datetime.now(timezone.utc))
```

## References

- [PRAW Documentation](https://praw.readthedocs.io/en/stable/)
- [Reddit API Documentation](https://www.reddit.com/dev/api/)
- [Reddit OAuth2 Guide](https://github.com/reddit-archive/reddit/wiki/OAuth2)
- [Prefect Documentation](https://docs.prefect.io/)

## Sources

- [PRAW Authentication Guide](https://praw.readthedocs.io/en/stable/getting_started/authentication.html)
- [PRAW Redditor Model](https://praw.readthedocs.io/en/stable/code_overview/models/redditor.html)
- [PRAW ListingGenerator](https://praw.readthedocs.io/en/stable/code_overview/other/listinggenerator.html)
- [Reddit API Rules](https://www.reddit.com/wiki/api)
