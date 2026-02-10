"""
Reddit Backup Workflow

Downloads Reddit saved posts, comments, and upvoted content. Supports:
- Saved posts with images, videos, and text content
- User comments history
- Upvoted submissions and comments
- Media downloads (images, videos, galleries)
- Idempotent backups using Reddit's unique IDs (t3_xxx, t1_xxx)

Requirements:
- praw library (pip install praw)
- requests for media downloads
- Valid Reddit OAuth2 credentials (script app type)

Authentication:
1. Create a Reddit app at https://www.reddit.com/prefs/apps
2. Choose "script" type
3. Set redirect uri to http://localhost:8080
4. Save client_id, client_secret, username, password

All timestamps are stored in UTC timezone for consistency.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.reddit_block import RedditBlock

try:
    import praw
    from praw.models import Comment, Submission
except ImportError:
    praw = None


BACKUP_DIR = Path("./backups/local/reddit")


@task(cache_policy=NO_CACHE)
def create_reddit_session(reddit_credentials: RedditBlock) -> "praw.Reddit":
    """
    Create and authenticate a Reddit session using PRAW.

    Args:
        reddit_credentials: Reddit credentials block

    Returns:
        Authenticated praw.Reddit instance
    """
    logger = get_run_logger()

    if praw is None:
        raise ImportError(
            "praw library is not installed. "
            "Run: pip install praw"
        )

    client_id = reddit_credentials.client_id.get_secret_value()
    client_secret = reddit_credentials.client_secret.get_secret_value()
    username = reddit_credentials.username.get_secret_value()
    password = reddit_credentials.password.get_secret_value()
    user_agent = reddit_credentials.user_agent

    logger.info(f"Creating Reddit session for user: {username}")

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )

        # Test authentication
        reddit.user.me()

        logger.info(f"Successfully authenticated as u/{username}")
        return reddit

    except Exception as e:
        logger.error(f"Failed to authenticate with Reddit: {e}")
        raise


@task(cache_policy=NO_CACHE)
def fetch_saved_posts(
    reddit: "praw.Reddit",
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Fetch user's saved posts and comments.
    Returns list sorted by Reddit ID for deterministic ordering.

    Args:
        reddit: Authenticated Reddit instance
        limit: Maximum number of items to fetch (None = all available)

    Returns:
        List of saved item dictionaries
    """
    logger = get_run_logger()

    logger.info(f"Fetching saved posts (limit={limit or 'all'})...")

    try:
        saved_items = []

        # Fetch saved items (includes both submissions and comments)
        for item in reddit.user.me().saved(limit=limit):
            item_data = extract_item_data(item)
            saved_items.append(item_data)

        # Sort by Reddit ID for deterministic ordering
        saved_items.sort(key=lambda x: x["reddit_id"])

        logger.info(f"Successfully fetched {len(saved_items)} saved items")
        return saved_items

    except Exception as e:
        logger.error(f"Failed to fetch saved posts: {e}")
        raise


@task(cache_policy=NO_CACHE)
def fetch_user_comments(
    reddit: "praw.Reddit",
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Fetch user's comment history.
    Returns list sorted by Reddit ID for deterministic ordering.

    Args:
        reddit: Authenticated Reddit instance
        limit: Maximum number of comments to fetch (None = all available)

    Returns:
        List of comment dictionaries
    """
    logger = get_run_logger()

    logger.info(f"Fetching user comments (limit={limit or 'all'})...")

    try:
        comments = []

        # Fetch user comments
        for comment in reddit.user.me().comments.new(limit=limit):
            comment_data = extract_comment_data(comment)
            comments.append(comment_data)

        # Sort by Reddit ID for deterministic ordering
        comments.sort(key=lambda x: x["reddit_id"])

        logger.info(f"Successfully fetched {len(comments)} comments")
        return comments

    except Exception as e:
        logger.error(f"Failed to fetch user comments: {e}")
        raise


@task(cache_policy=NO_CACHE)
def fetch_upvoted_content(
    reddit: "praw.Reddit",
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Fetch user's upvoted submissions and comments.
    Returns list sorted by Reddit ID for deterministic ordering.

    Args:
        reddit: Authenticated Reddit instance
        limit: Maximum number of items to fetch (None = all available)

    Returns:
        List of upvoted item dictionaries
    """
    logger = get_run_logger()

    logger.info(f"Fetching upvoted content (limit={limit or 'all'})...")

    try:
        upvoted_items = []

        # Fetch upvoted items (includes both submissions and comments)
        for item in reddit.user.me().upvoted(limit=limit):
            item_data = extract_item_data(item)
            upvoted_items.append(item_data)

        # Sort by Reddit ID for deterministic ordering
        upvoted_items.sort(key=lambda x: x["reddit_id"])

        logger.info(f"Successfully fetched {len(upvoted_items)} upvoted items")
        return upvoted_items

    except Exception as e:
        logger.error(f"Failed to fetch upvoted content: {e}")
        raise


def extract_item_data(item) -> dict:
    """
    Extract data from a Reddit item (Submission or Comment).
    Handles both types uniformly.

    Args:
        item: PRAW Submission or Comment object

    Returns:
        Dictionary with item data
    """
    if isinstance(item, Submission):
        return extract_submission_data(item)
    elif isinstance(item, Comment):
        return extract_comment_data(item)
    else:
        # Fallback for unknown types
        return {
            "reddit_id": getattr(item, "id", "unknown"),
            "type": "unknown",
            "created_utc": getattr(item, "created_utc", None),
        }


def extract_submission_data(submission: "Submission") -> dict:
    """
    Extract data from a Reddit submission (post).

    Args:
        submission: PRAW Submission object

    Returns:
        Dictionary with submission data
    """
    # Convert Unix timestamp to UTC datetime
    created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

    data = {
        "reddit_id": submission.id,
        "fullname": submission.name,  # e.g., t3_abc123
        "type": "submission",
        "title": submission.title,
        "author": str(submission.author) if submission.author else "[deleted]",
        "subreddit": str(submission.subreddit),
        "url": submission.url,
        "permalink": f"https://www.reddit.com{submission.permalink}",
        "selftext": submission.selftext,
        "is_self": submission.is_self,
        "score": submission.score,
        "num_comments": submission.num_comments,
        "created_utc": created_utc.isoformat(),
        "over_18": submission.over_18,
        "spoiler": submission.spoiler,
        "stickied": submission.stickied,
        "locked": submission.locked,
        "domain": submission.domain,
    }

    # Handle different media types
    if hasattr(submission, "is_video") and submission.is_video:
        data["media_type"] = "video"
        if hasattr(submission, "media") and submission.media:
            data["media_url"] = submission.media.get("reddit_video", {}).get("fallback_url")
    elif hasattr(submission, "is_gallery") and submission.is_gallery:
        data["media_type"] = "gallery"
        # Extract gallery URLs
        gallery_urls = []
        if hasattr(submission, "media_metadata") and hasattr(submission, "gallery_data") and submission.gallery_data:
            for item_id in submission.gallery_data["items"]:
                media_id = item_id["media_id"]
                media_info = submission.media_metadata[media_id]
                if "s" in media_info and "u" in media_info["s"]:
                    gallery_urls.append(media_info["s"]["u"])
            data["gallery_urls"] = gallery_urls
    elif submission.url and any(
        submission.url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]
    ):
        data["media_type"] = "image"
        data["media_url"] = submission.url
    else:
        data["media_type"] = "link"

    return data


def extract_comment_data(comment: "Comment") -> dict:
    """
    Extract data from a Reddit comment.

    Args:
        comment: PRAW Comment object

    Returns:
        Dictionary with comment data
    """
    # Convert Unix timestamp to UTC datetime
    created_utc = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)

    # Get parent context
    parent_id = comment.parent_id
    parent_type = "submission" if parent_id.startswith("t3_") else "comment"

    data = {
        "reddit_id": comment.id,
        "fullname": comment.name,  # e.g., t1_abc123
        "type": "comment",
        "body": comment.body,
        "author": str(comment.author) if comment.author else "[deleted]",
        "subreddit": str(comment.subreddit),
        "permalink": f"https://www.reddit.com{comment.permalink}",
        "score": comment.score,
        "created_utc": created_utc.isoformat(),
        "edited": bool(comment.edited),
        "stickied": comment.stickied,
        "parent_id": parent_id,
        "parent_type": parent_type,
        "submission_id": comment.submission.id if hasattr(comment, "submission") else None,
        "submission_title": comment.submission.title if hasattr(comment, "submission") else None,
    }

    return data


def download_media(
    item: dict,
    media_dir: Path,
    download_archive: set[str],
) -> Optional[Path]:
    """
    Download media for a Reddit item if not already downloaded.
    Uses download archive for idempotency.

    Args:
        item: Item dictionary with media information
        media_dir: Directory to save media files
        download_archive: Set of already-downloaded Reddit IDs

    Returns:
        Path to downloaded media file, or None if no media or already exists
    """
    logger = get_run_logger()

    reddit_id = item["reddit_id"]

    # Check download archive for idempotency
    if reddit_id in download_archive:
        logger.debug(f"Item {reddit_id} already downloaded, skipping...")
        return None

    # Only download if there's media
    if item.get("media_type") not in ["image", "video"]:
        return None

    media_url = item.get("media_url")
    if not media_url:
        return None

    # Determine file extension
    parsed_url = urlparse(media_url)
    file_ext = Path(parsed_url.path).suffix or ".jpg"

    # Create filename using Reddit ID for idempotency
    media_filename = f"{reddit_id}{file_ext}"
    media_path = media_dir / media_filename

    # Check if file already exists (additional safety check)
    if media_path.exists():
        logger.debug(f"Media file {media_path} already exists, skipping download...")
        download_archive.add(reddit_id)
        return media_path

    try:
        # Download media
        response = requests.get(media_url, timeout=30)
        response.raise_for_status()

        # Save to disk
        media_dir.mkdir(parents=True, exist_ok=True)
        with open(media_path, "wb") as f:
            f.write(response.content)

        logger.info(f"Downloaded media for {reddit_id} to {media_path}")

        # Add to archive
        download_archive.add(reddit_id)

        return media_path

    except Exception as e:
        logger.error(f"Failed to download media for {reddit_id}: {e}")
        return None


@task(cache_policy=NO_CACHE)
def save_items_to_disk(
    items: list[dict],
    username: str,
    content_type: str,
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
    download_media_files: bool = True,
) -> dict:
    """
    Save Reddit items to disk with metadata.
    Uses download archive for idempotent media downloads.

    Args:
        items: List of item dictionaries
        username: Reddit username
        content_type: Type of content (saved, comments, upvoted)
        snapshot_date: Date for this backup snapshot (UTC)
        output_dir: Base backup directory
        download_media_files: Whether to download media files

    Returns:
        Dictionary with save statistics
    """
    logger = get_run_logger()

    # Ensure snapshot_date is UTC-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    # Create directory structure: reddit/{username}/{content_type}/{snapshot_date}/
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    content_dir = output_dir / username / content_type / snapshot_str
    content_dir.mkdir(parents=True, exist_ok=True)

    # Load download archive for idempotency
    archive_file = output_dir / username / content_type / "download_archive.txt"
    download_archive = set()
    if archive_file.exists():
        with open(archive_file, "r") as f:
            download_archive = set(line.strip() for line in f if line.strip())

    # Check if items file already exists (idempotency)
    items_file = content_dir / f"{content_type}.json"
    if items_file.exists():
        logger.info(f"Items file already exists at {items_file}, skipping save...")
        with open(items_file, "r") as f:
            existing_data = json.load(f)
        return {
            "items_saved": len(existing_data.get("items", [])),
            "items_file": str(items_file),
            "already_existed": True,
            "media_downloaded": 0,
        }

    # Download media files if requested
    media_downloaded = 0
    if download_media_files:
        media_dir = content_dir / "media"
        for item in items:
            if download_media(item, media_dir, download_archive):
                media_downloaded += 1

    # Save download archive
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    with open(archive_file, "w") as f:
        for reddit_id in sorted(download_archive):
            f.write(f"{reddit_id}\n")

    # Save all items to a single JSON file
    items_data = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "backup_timestamp": snapshot_date.isoformat(),
        "username": username,
        "content_type": content_type,
        "item_count": len(items),
        "items": items,
    }

    with open(items_file, "w") as f:
        json.dump(items_data, f, indent=2, sort_keys=True, default=str)

    logger.info(f"Saved {len(items)} items to {items_file}")

    # Create per-item files for easier searching
    for item in items:
        reddit_id = item.get("reddit_id")
        if reddit_id:
            item_file = content_dir / f"{reddit_id}.json"
            with open(item_file, "w") as f:
                json.dump(item, f, indent=2, sort_keys=True, default=str)

    logger.info(f"Created {len(items)} individual item files")

    return {
        "items_saved": len(items),
        "items_file": str(items_file),
        "individual_files": len(items),
        "media_downloaded": media_downloaded,
        "already_existed": False,
    }


@task()
def check_snapshot_exists(
    username: str,
    content_type: str,
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
) -> bool:
    """
    Check if a snapshot already exists for the given date and content type.
    Returns True if the snapshot directory and items file exist.
    """
    logger = get_run_logger()
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    snapshot_dir = output_dir / username / content_type / snapshot_str
    items_file = snapshot_dir / f"{content_type}.json"

    if snapshot_dir.exists() and items_file.exists():
        logger.info(f"Snapshot for {content_type} on {snapshot_str} already exists")
        return True
    return False


@task()
def save_backup_manifest(
    username: str,
    content_type: str,
    snapshot_date: datetime,
    save_result: dict,
    workflow_start: float,
    output_dir: Path = BACKUP_DIR,
) -> Path:
    """
    Save a manifest file with backup metadata.

    Args:
        username: Reddit username
        content_type: Type of content (saved, comments, upvoted)
        snapshot_date: Date for this backup snapshot
        save_result: Result from save_items_to_disk
        workflow_start: Workflow start timestamp
        output_dir: Base backup directory

    Returns:
        Path to manifest file
    """
    logger = get_run_logger()

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    manifest_path = (
        output_dir / username / content_type / f"backup_manifest_{snapshot_str}.json"
    )

    manifest = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_version": "1.0.0",
        "python_version": sys.version,
        "username": username,
        "content_type": content_type,
        "item_count": save_result.get("items_saved", 0),
        "media_downloaded": save_result.get("media_downloaded", 0),
        "processing_duration_seconds": time.time() - workflow_start,
        "already_existed": save_result.get("already_existed", False),
        "items_file": save_result.get("items_file"),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"Saved backup manifest to {manifest_path}")
    return manifest_path


@flow(name="backup-reddit-content")
def backup_reddit_content(
    snapshot_date: datetime,
    credentials_block_name: str = "reddit-credentials",
    content_types: list[str] = ["saved", "comments", "upvoted"],
    limit: Optional[int] = None,
    download_media: bool = True,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Main flow to backup Reddit content.

    Args:
        snapshot_date: Date for this backup snapshot (for idempotency, UTC)
        credentials_block_name: Name of the Prefect Reddit credentials block
        content_types: List of content types to backup (saved, comments, upvoted)
        limit: Maximum items to fetch per content type (None = all available)
        download_media: Whether to download media files
        output_dir: Base directory for backups

    Returns:
        Dictionary with backup results
    """
    logger = get_run_logger()
    workflow_start = time.time()

    # Ensure snapshot_date is timezone-aware (UTC)
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    logger.info(
        f"Starting Reddit backup (snapshot date: {snapshot_date.isoformat()})"
    )
    logger.info(f"Content types: {', '.join(content_types)}")

    # Load credentials
    logger.info(f"Loading Reddit credentials from block: {credentials_block_name}")
    reddit_credentials = RedditBlock.load(credentials_block_name)
    username = reddit_credentials.username.get_secret_value()

    # Create authenticated session
    reddit = create_reddit_session(reddit_credentials)

    results = {}

    # Process each content type
    for content_type in content_types:
        logger.info(f"Processing {content_type}...")

        # Check if snapshot already exists (idempotency)
        if check_snapshot_exists(username, content_type, snapshot_date, output_dir):
            logger.info(
                f"Snapshot for {content_type} already exists. Skipping."
            )
            results[content_type] = {
                "success": True,
                "message": "Snapshot already exists",
                "snapshot_date": snapshot_date.isoformat(),
            }
            continue

        # Fetch content based on type
        try:
            if content_type == "saved":
                items = fetch_saved_posts(reddit, limit=limit)
            elif content_type == "comments":
                items = fetch_user_comments(reddit, limit=limit)
            elif content_type == "upvoted":
                items = fetch_upvoted_content(reddit, limit=limit)
            else:
                logger.warning(f"Unknown content type: {content_type}, skipping...")
                continue

            if not items:
                logger.warning(f"No {content_type} items found")
                results[content_type] = {
                    "success": False,
                    "message": "No items found",
                    "snapshot_date": snapshot_date.isoformat(),
                }
                continue

            # Save items to disk
            save_result = save_items_to_disk(
                items=items,
                username=username,
                content_type=content_type,
                snapshot_date=snapshot_date,
                output_dir=output_dir,
                download_media_files=download_media,
            )

            # Save backup manifest
            manifest_path = save_backup_manifest(
                username=username,
                content_type=content_type,
                snapshot_date=snapshot_date,
                save_result=save_result,
                workflow_start=workflow_start,
                output_dir=output_dir,
            )

            logger.info(
                f"Successfully backed up {save_result['items_saved']} {content_type} items"
            )
            logger.info(f"Manifest saved to {manifest_path}")

            results[content_type] = {
                "success": True,
                "item_count": save_result["items_saved"],
                "items_file": save_result["items_file"],
                "media_downloaded": save_result.get("media_downloaded", 0),
                "manifest_file": str(manifest_path),
                "snapshot_date": snapshot_date.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to backup {content_type}: {e}")
            results[content_type] = {
                "success": False,
                "error": str(e),
                "snapshot_date": snapshot_date.isoformat(),
            }

    return results


if __name__ == "__main__":
    # Example usage - backup all content types
    backup_reddit_content(
        snapshot_date=datetime.now(timezone.utc),
        content_types=["saved", "comments", "upvoted"],
        limit=10,  # Limit for testing, set to None for full backup
        download_media=True,
    )
