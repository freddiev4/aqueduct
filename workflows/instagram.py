import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

try:
    import instaloader
except ImportError:
    raise ImportError(
        "instaloader is required. Install it with: uv pip install instaloader"
    )


@task(cache_policy=NO_CACHE)
def download_user_posts(
    username: str,
    password: Optional[str],
    snapshot_date: datetime,
    local_backup_dir: Path = Path("./backups/local"),
    max_posts: Optional[int] = None,
) -> dict:
    """
    Download all posts from the authenticated user's profile up to a snapshot date.

    Args:
        username: Instagram username
        password: Instagram password (optional, will prompt if not provided)
        snapshot_date: Only download posts created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_posts: Maximum number of posts to download (None for all)

    Returns:
        Dictionary with download statistics
    """
    loader = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=True,
        download_geotags=False,
        download_comments=False,  # User doesn't care about comments
        save_metadata=True,
        compress_json=False,
        post_metadata_txt_pattern="",
    )
    
    # Create backup directory structure
    backup_path = local_backup_dir / "instagram" / username / "posts"
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Set download directory
    loader.dirname_pattern = str(backup_path)
    
    # Login if password is provided
    if password:
        try:
            loader.login(username, password)
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            print("Two-factor authentication required. Please run manually first to set up 2FA.")
            raise
        except instaloader.exceptions.BadCredentialsException:
            print("Invalid credentials. Please check your username and password.")
            raise
    else:
        # Try to load session from previous login
        try:
            loader.load_session_from_file(username)
        except FileNotFoundError:
            print("No saved session found. Please provide password or login manually first.")
            raise
    
    # Get profile
    profile = instaloader.Profile.from_username(loader.context, username)
    
    # Download posts
    post_count = 0
    downloaded_posts = []

    print(f"Starting download of posts for {username} (snapshot date: {snapshot_date.isoformat()})...")

    # Collect all posts and sort deterministically
    all_posts = []
    for post in profile.get_posts():
        # Get post date and ensure UTC timezone
        post_date = post.date_utc
        if post_date:
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)
            elif post_date.tzinfo != timezone.utc:
                post_date = post_date.astimezone(timezone.utc)

            # Apply temporal filtering - only include posts up to snapshot_date
            if post_date > snapshot_date:
                continue

        all_posts.append(post)

    # Sort posts by date (newest first) for deterministic ordering
    all_posts.sort(key=lambda p: p.date_utc if p.date_utc else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Download posts
    for post in all_posts:
        if max_posts and post_count >= max_posts:
            break

        try:
            loader.download_post(post, target=username)

            # Ensure date is properly formatted in UTC
            post_date = post.date_utc
            if post_date:
                if post_date.tzinfo is None:
                    post_date = post_date.replace(tzinfo=timezone.utc)
                elif post_date.tzinfo != timezone.utc:
                    post_date = post_date.astimezone(timezone.utc)
                date_str = post_date.isoformat()
            else:
                date_str = None

            downloaded_posts.append({
                "shortcode": post.shortcode,
                "date": date_str,
                "is_video": post.is_video,
                "caption": post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else post.caption,
            })
            post_count += 1
            print(f"Downloaded post {post_count}: {post.shortcode}")
        except Exception as e:
            print(f"Error downloading post {post.shortcode}: {e}")
            continue
    
    # Save metadata summary
    metadata_file = backup_path / "posts_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "username": username,
            "total_posts_downloaded": post_count,
            "snapshot_date": snapshot_date.isoformat(),
            "posts": downloaded_posts,
        }, f, indent=2, sort_keys=True)
    
    print(f"Downloaded {post_count} posts to {backup_path}")
    
    return {
        "username": username,
        "post_count": post_count,
        "backup_path": str(backup_path),
        "posts": downloaded_posts,
    }


@task(cache_policy=NO_CACHE)
def download_saved_posts(
    username: str,
    password: Optional[str],
    snapshot_date: datetime,
    local_backup_dir: Path = Path("./backups/local"),
    max_posts: Optional[int] = None,
) -> dict:
    """
    Download all saved/bookmarked posts from the authenticated user's profile up to a snapshot date.

    Args:
        username: Instagram username
        password: Instagram password (optional, will prompt if not provided)
        snapshot_date: Only download posts created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_posts: Maximum number of saved posts to download (None for all)

    Returns:
        Dictionary with download statistics
    """
    loader = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=True,
        download_geotags=False,
        download_comments=False,  # User doesn't care about comments
        save_metadata=True,
        compress_json=False,
        post_metadata_txt_pattern="",
    )
    
    # Create backup directory structure
    backup_path = local_backup_dir / "instagram" / username / "saved_posts"
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Set download directory
    loader.dirname_pattern = str(backup_path)
    
    # Login if password is provided
    if password:
        try:
            loader.login(username, password)
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            print("Two-factor authentication required. Please run manually first to set up 2FA.")
            raise
        except instaloader.exceptions.BadCredentialsException:
            print("Invalid credentials. Please check your username and password.")
            raise
    else:
        # Try to load session from previous login
        try:
            loader.load_session_from_file(username)
        except FileNotFoundError:
            print("No saved session found. Please provide password or login manually first.")
            raise
    
    # Get profile
    profile = instaloader.Profile.from_username(loader.context, username)
    
    # Download saved posts
    post_count = 0
    downloaded_posts = []

    print(f"Starting download of saved posts for {username} (snapshot date: {snapshot_date.isoformat()})...")

    # Collect all saved posts and sort deterministically
    all_saved_posts = []
    for post in profile.get_saved_posts():
        # Get post date and ensure UTC timezone
        post_date = post.date_utc
        if post_date:
            if post_date.tzinfo is None:
                post_date = post_date.replace(tzinfo=timezone.utc)
            elif post_date.tzinfo != timezone.utc:
                post_date = post_date.astimezone(timezone.utc)

            # Apply temporal filtering - only include posts up to snapshot_date
            if post_date > snapshot_date:
                continue

        all_saved_posts.append(post)

    # Sort posts by date (newest first) for deterministic ordering
    all_saved_posts.sort(key=lambda p: p.date_utc if p.date_utc else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Download saved posts
    for post in all_saved_posts:
        if max_posts and post_count >= max_posts:
            break

        try:
            # Get the original post owner's username for organization
            owner_username = post.owner_username

            # Create subdirectory for each post owner
            owner_backup_path = backup_path / owner_username
            owner_backup_path.mkdir(parents=True, exist_ok=True)

            # Temporarily set directory for this post
            original_dirname = loader.dirname_pattern
            loader.dirname_pattern = str(owner_backup_path)

            loader.download_post(post, target=owner_username)

            # Restore original directory pattern
            loader.dirname_pattern = original_dirname

            # Ensure date is properly formatted in UTC
            post_date = post.date_utc
            if post_date:
                if post_date.tzinfo is None:
                    post_date = post_date.replace(tzinfo=timezone.utc)
                elif post_date.tzinfo != timezone.utc:
                    post_date = post_date.astimezone(timezone.utc)
                date_str = post_date.isoformat()
            else:
                date_str = None

            downloaded_posts.append({
                "shortcode": post.shortcode,
                "owner_username": owner_username,
                "date": date_str,
                "is_video": post.is_video,
                "caption": post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else post.caption,
            })
            post_count += 1
            print(f"Downloaded saved post {post_count}: {post.shortcode} from @{owner_username}")
        except Exception as e:
            print(f"Error downloading saved post {post.shortcode}: {e}")
            continue
    
    # Save metadata summary
    metadata_file = backup_path / "saved_posts_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "username": username,
            "total_saved_posts_downloaded": post_count,
            "snapshot_date": snapshot_date.isoformat(),
            "posts": downloaded_posts,
        }, f, indent=2, sort_keys=True)
    
    print(f"Downloaded {post_count} saved posts to {backup_path}")
    
    return {
        "username": username,
        "saved_post_count": post_count,
        "backup_path": str(backup_path),
        "posts": downloaded_posts,
    }


@flow()
def backup_instagram(
    username: str,
    password: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    download_posts: bool = True,
    download_saved_posts: bool = True,
    max_posts: Optional[int] = None,
    max_saved_posts: Optional[int] = None,
    local_backup_dir: Path = Path("./backups/local"),
):
    """
    Main flow to backup Instagram posts and saved posts up to a snapshot date.

    Args:
        username: Instagram username
        password: Instagram password (optional, will use saved session if not provided)
        snapshot_date: Only download posts created before or on this date (UTC). Defaults to current time.
        download_posts: Whether to download user's own posts
        download_saved_posts: Whether to download saved/bookmarked posts
        max_posts: Maximum number of posts to download (None for all)
        max_saved_posts: Maximum number of saved posts to download (None for all)
        local_backup_dir: Base directory for backups
    """
    # Default to current UTC time if no snapshot_date provided
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc)
    # Ensure snapshot_date is timezone-aware UTC
    elif snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)
    elif snapshot_date.tzinfo != timezone.utc:
        snapshot_date = snapshot_date.astimezone(timezone.utc)
    results = {}
    
    if download_posts:
        print(f"Backing up posts for {username}...")
        posts_result = download_user_posts(
            username=username,
            password=password,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_posts=max_posts,
        )
        results["posts"] = posts_result

    if download_saved_posts:
        print(f"Backing up saved posts for {username}...")
        saved_posts_result = download_saved_posts(
            username=username,
            password=password,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_posts=max_saved_posts,
        )
        results["saved_posts"] = saved_posts_result
    
    print(f"Instagram backup completed for {username}")
    print(f"  - Posts downloaded: {results.get('posts', {}).get('post_count', 0)}")
    print(f"  - Saved posts downloaded: {results.get('saved_posts', {}).get('saved_post_count', 0)}")
    
    return results


if __name__ == "__main__":
    # Example usage - you can modify these parameters
    backup_instagram(
        username="your_username",  # Replace with your Instagram username
        password=None,  # Set to your password or None to use saved session
        download_posts=True,
        download_saved_posts=True,
        max_posts=None,  # Set to a number to limit posts, or None for all
        max_saved_posts=None,  # Set to a number to limit saved posts, or None for all
    )

