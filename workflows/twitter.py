import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

try:
    import tweepy
except ImportError:
    raise ImportError(
        "tweepy is required. Install it with: uv pip install tweepy"
    )


def download_media(url: str, filepath: Path) -> bool:
    """
    Download media (image/video) from URL to filepath.
    
    Args:
        url: URL of the media to download
        filepath: Path where to save the media
    
    Returns:
        True if successful, False otherwise
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error downloading media from {url}: {e}")
        return False


def extract_media_urls(tweet_data: dict) -> list[dict]:
    """
    Extract media URLs from tweet data.
    
    Args:
        tweet_data: Tweet data dictionary
    
    Returns:
        List of media dictionaries with type and url
    """
    media_list = []
    
    # Check for media in attachments
    if "attachments" in tweet_data and "media_keys" in tweet_data["attachments"]:
        # Media details are in includes.media
        if "includes" in tweet_data and "media" in tweet_data["includes"]:
            for media_key in tweet_data["attachments"]["media_keys"]:
                for media in tweet_data["includes"]["media"]:
                    if media.get("media_key") == media_key:
                        media_info = {
                            "type": media.get("type", "unknown"),
                            "media_key": media_key,
                        }
                        
                        if media.get("type") == "photo":
                            media_info["url"] = media.get("url")
                        elif media.get("type") == "video":
                            # Get the best quality video URL
                            variants = media.get("variants", [])
                            video_url = None
                            bitrate = 0
                            for variant in variants:
                                if variant.get("content_type") == "video/mp4":
                                    if variant.get("bit_rate", 0) > bitrate:
                                        bitrate = variant.get("bit_rate", 0)
                                        video_url = variant.get("url")
                            media_info["url"] = video_url
                            media_info["preview_image_url"] = media.get("preview_image_url")
                        elif media.get("type") == "animated_gif":
                            variants = media.get("variants", [])
                            if variants:
                                media_info["url"] = variants[0].get("url")
                        
                        media_list.append(media_info)
    
    return media_list


@task(cache_policy=NO_CACHE)
def download_user_tweets(
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    username: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    local_backup_dir: Path = Path("./backups/local"),
    max_tweets: Optional[int] = None,
    include_replies: bool = False,
) -> dict:
    """
    Download all tweets from the authenticated user's profile up to a snapshot date.

    Args:
        bearer_token: Twitter Bearer Token (for OAuth 2.0)
        api_key: Twitter API Key (for OAuth 1.0a)
        api_secret: Twitter API Secret (for OAuth 1.0a)
        access_token: Twitter Access Token (for OAuth 1.0a)
        access_token_secret: Twitter Access Token Secret (for OAuth 1.0a)
        username: Twitter username (optional, will use authenticated user if not provided)
        snapshot_date: Only download tweets created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_tweets: Maximum number of tweets to download (None for all)
        include_replies: Whether to include replies in the download

    Returns:
        Dictionary with download statistics
    """
    # Initialize Twitter API client
    if bearer_token:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
    elif api_key and api_secret and access_token and access_token_secret:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True,
        )
    else:
        raise ValueError(
            "Either bearer_token or (api_key, api_secret, access_token, access_token_secret) must be provided"
        )
    
    # Get user ID
    if username:
        user = client.get_user(username=username)
    else:
        user = client.get_me()
    
    if not user.data:
        raise ValueError(f"User not found: {username if username else 'authenticated user'}")
    
    user_id = user.data.id
    username = user.data.username
    
    # Create backup directory structure
    backup_path = local_backup_dir / "twitter" / username / "tweets"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)
    
    # Download tweets
    tweet_count = 0
    downloaded_tweets = []
    
    print(f"Starting download of tweets for @{username}...")
    
    # Get user's tweets
    tweet_fields = [
        "id", "text", "created_at", "author_id", "public_metrics",
        "attachments", "entities", "referenced_tweets", "in_reply_to_user_id"
    ]
    expansions = ["attachments.media_keys", "author_id"]
    media_fields = ["type", "url", "preview_image_url", "variants", "media_key"]
    
    exclude_list = [] if include_replies else ["retweets"]
    paginator = tweepy.Paginator(
        client.get_users_tweets,
        id=user_id,
        max_results=100,
        tweet_fields=tweet_fields,
        expansions=expansions,
        media_fields=media_fields,
        exclude=exclude_list,
        end_time=snapshot_date,
    )
    
    for page in paginator:
        if max_tweets and tweet_count >= max_tweets:
            break
        
        # Process tweets in this page
        tweets = page.data or []
        includes = page.includes or {}
        media_dict = {}
        
        # Build media dictionary from includes
        if "media" in includes:
            for media in includes["media"]:
                media_dict[media.media_key] = media
        
        for tweet in tweets:
            if max_tweets and tweet_count >= max_tweets:
                break
            
            try:
                # Convert tweet to dict for JSON serialization
                # Handle referenced_tweets properly
                referenced_tweets_data = None
                if hasattr(tweet, "referenced_tweets") and tweet.referenced_tweets:
                    referenced_tweets_data = [
                        {"type": rt.type, "id": rt.id} for rt in tweet.referenced_tweets
                    ]
                
                tweet_data = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author_id": tweet.author_id,
                    "public_metrics": tweet.public_metrics,
                    "referenced_tweets": referenced_tweets_data,
                    "in_reply_to_user_id": getattr(tweet, "in_reply_to_user_id", None),
                }
                
                # Get media attachments
                media_list = []
                if hasattr(tweet, "attachments") and tweet.attachments:
                    if hasattr(tweet.attachments, "media_keys") and tweet.attachments.media_keys:
                        for media_key in tweet.attachments.media_keys:
                            if media_key in media_dict:
                                media = media_dict[media_key]
                                media_info = {
                                    "type": media.type,
                                    "media_key": media_key,
                                }
                                
                                if media.type == "photo" and hasattr(media, "url"):
                                    media_info["url"] = media.url
                                elif media.type == "video":
                                    if hasattr(media, "variants") and media.variants:
                                        # Get highest quality video
                                        best_variant = max(
                                            [v for v in media.variants if hasattr(v, "bit_rate") and v.bit_rate],
                                            key=lambda v: v.bit_rate,
                                            default=None
                                        )
                                        if best_variant:
                                            media_info["url"] = best_variant.url
                                    if hasattr(media, "preview_image_url"):
                                        media_info["preview_image_url"] = media.preview_image_url
                                elif media.type == "animated_gif":
                                    if hasattr(media, "variants") and media.variants:
                                        media_info["url"] = media.variants[0].url
                                
                                media_list.append(media_info)
                
                # Download media files
                media_files = []
                for idx, media_info in enumerate(media_list):
                    if "url" in media_info:
                        # Determine file extension
                        ext = "jpg"
                        if media_info["type"] == "video":
                            ext = "mp4"
                        elif media_info["type"] == "animated_gif":
                            ext = "gif"
                        
                        media_filename = f"{tweet.id}_{idx}.{ext}"
                        media_filepath = media_path / media_filename
                        
                        if download_media(media_info["url"], media_filepath):
                            media_files.append({
                                "filename": media_filename,
                                "type": media_info["type"],
                                "url": media_info["url"],
                            })
                
                tweet_data["media"] = media_files
                
                # Get replies/comments if < 100
                reply_count = 0
                if tweet.public_metrics:
                    reply_count = tweet.public_metrics.get("reply_count", 0)
                
                if reply_count > 0 and reply_count < 100:
                    try:
                        # Get conversation replies using search
                        # Note: This requires Academic Research access for full conversation history
                        # For basic access, we'll try to get recent replies
                        replies_paginator = tweepy.Paginator(
                            client.search_recent_tweets,
                            query=f"conversation_id:{tweet.id}",
                            max_results=min(100, reply_count),
                            tweet_fields=["id", "text", "created_at", "author_id"],
                        )
                        
                        replies = []
                        for replies_page in replies_paginator:
                            if replies_page.data:
                                for reply in replies_page.data:
                                    if reply.id != tweet.id:  # Don't include the original tweet
                                        replies.append({
                                            "id": reply.id,
                                            "text": reply.text,
                                            "created_at": reply.created_at.isoformat() if reply.created_at else None,
                                            "author_id": reply.author_id,
                                        })
                        
                        if replies:
                            tweet_data["replies"] = replies[:100]  # Limit to 100
                    except Exception as e:
                        # Search might not be available or might fail - that's okay
                        print(f"Note: Could not fetch replies for tweet {tweet.id}: {e}")
                
                # Save individual tweet JSON
                tweet_file = backup_path / f"{tweet.id}.json"
                with open(tweet_file, "w") as f:
                    json.dump(tweet_data, f, indent=2, sort_keys=True)
                
                downloaded_tweets.append({
                    "id": tweet.id,
                    "date": tweet_data["created_at"],
                    "text_preview": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                    "media_count": len(media_files),
                    "reply_count": tweet.public_metrics.get("reply_count", 0) if tweet.public_metrics else 0,
                })
                
                tweet_count += 1
                print(f"Downloaded tweet {tweet_count}: {tweet.id}")
                
            except Exception as e:
                print(f"Error processing tweet {tweet.id}: {e}")
                continue
    
    # Save metadata summary
    metadata_file = backup_path / "tweets_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "username": username,
            "user_id": user_id,
            "total_tweets_downloaded": tweet_count,
            "snapshot_date": snapshot_date.isoformat(),
            "tweets": downloaded_tweets,
        }, f, indent=2, sort_keys=True)
    
    print(f"Downloaded {tweet_count} tweets to {backup_path}")
    
    return {
        "username": username,
        "tweet_count": tweet_count,
        "backup_path": str(backup_path),
        "tweets": downloaded_tweets,
    }


@task(cache_policy=NO_CACHE)
def download_bookmarks(
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    username: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    local_backup_dir: Path = Path("./backups/local"),
    max_bookmarks: Optional[int] = None,
) -> dict:
    """
    Download all bookmarked tweets from the authenticated user's profile up to a snapshot date.

    Args:
        bearer_token: Twitter Bearer Token (for OAuth 2.0)
        api_key: Twitter API Key (for OAuth 1.0a)
        api_secret: Twitter API Secret (for OAuth 1.0a)
        access_token: Twitter Access Token (for OAuth 1.0a)
        access_token_secret: Twitter Access Token Secret (for OAuth 1.0a)
        username: Twitter username (optional, will use authenticated user if not provided)
        snapshot_date: Only download tweets created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_bookmarks: Maximum number of bookmarks to download (None for all)

    Returns:
        Dictionary with download statistics
    """
    # Initialize Twitter API client
    if bearer_token:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
    elif api_key and api_secret and access_token and access_token_secret:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True,
        )
    else:
        raise ValueError(
            "Either bearer_token or (api_key, api_secret, access_token, access_token_secret) must be provided"
        )
    
    # Get user ID
    if username:
        user = client.get_user(username=username)
    else:
        user = client.get_me()
    
    if not user.data:
        raise ValueError(f"User not found: {username if username else 'authenticated user'}")
    
    user_id = user.data.id
    username = user.data.username
    
    # Create backup directory structure
    backup_path = local_backup_dir / "twitter" / username / "bookmarks"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)
    
    # Download bookmarks
    bookmark_count = 0
    downloaded_bookmarks = []
    
    print(f"Starting download of bookmarks for @{username}...")
    
    # Get user's bookmarks
    tweet_fields = [
        "id", "text", "created_at", "author_id", "public_metrics",
        "attachments", "entities", "referenced_tweets"
    ]
    expansions = ["attachments.media_keys", "author_id"]
    media_fields = ["type", "url", "preview_image_url", "variants", "media_key"]
    
    paginator = tweepy.Paginator(
        client.get_bookmarks,
        max_results=100,
        tweet_fields=tweet_fields,
        expansions=expansions,
        media_fields=media_fields,
        end_time=snapshot_date,
    )
    
    for page in paginator:
        if max_bookmarks and bookmark_count >= max_bookmarks:
            break
        
        # Process bookmarks in this page
        tweets = page.data or []
        includes = page.includes or {}
        media_dict = {}
        
        # Build media dictionary from includes
        if "media" in includes:
            for media in includes["media"]:
                media_dict[media.media_key] = media
        
        for tweet in tweets:
            if max_bookmarks and bookmark_count >= max_bookmarks:
                break
            
            try:
                # Handle referenced_tweets properly
                referenced_tweets_data = None
                if hasattr(tweet, "referenced_tweets") and tweet.referenced_tweets:
                    referenced_tweets_data = [
                        {"type": rt.type, "id": rt.id} for rt in tweet.referenced_tweets
                    ]
                
                # Convert tweet to dict for JSON serialization
                tweet_data = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author_id": tweet.author_id,
                    "public_metrics": tweet.public_metrics,
                    "referenced_tweets": referenced_tweets_data,
                }
                
                # Get media attachments
                media_list = []
                if hasattr(tweet, "attachments") and tweet.attachments:
                    if hasattr(tweet.attachments, "media_keys") and tweet.attachments.media_keys:
                        for media_key in tweet.attachments.media_keys:
                            if media_key in media_dict:
                                media = media_dict[media_key]
                                media_info = {
                                    "type": media.type,
                                    "media_key": media_key,
                                }
                                
                                if media.type == "photo" and hasattr(media, "url"):
                                    media_info["url"] = media.url
                                elif media.type == "video":
                                    if hasattr(media, "variants") and media.variants:
                                        best_variant = max(
                                            [v for v in media.variants if hasattr(v, "bit_rate") and v.bit_rate],
                                            key=lambda v: v.bit_rate,
                                            default=None
                                        )
                                        if best_variant:
                                            media_info["url"] = best_variant.url
                                    if hasattr(media, "preview_image_url"):
                                        media_info["preview_image_url"] = media.preview_image_url
                                elif media.type == "animated_gif":
                                    if hasattr(media, "variants") and media.variants:
                                        media_info["url"] = media.variants[0].url
                                
                                media_list.append(media_info)
                
                # Download media files
                media_files = []
                for idx, media_info in enumerate(media_list):
                    if "url" in media_info:
                        ext = "jpg"
                        if media_info["type"] == "video":
                            ext = "mp4"
                        elif media_info["type"] == "animated_gif":
                            ext = "gif"
                        
                        media_filename = f"{tweet.id}_{idx}.{ext}"
                        media_filepath = media_path / media_filename
                        
                        if download_media(media_info["url"], media_filepath):
                            media_files.append({
                                "filename": media_filename,
                                "type": media_info["type"],
                                "url": media_info["url"],
                            })
                
                tweet_data["media"] = media_files
                
                # Get replies/comments if < 100
                reply_count = 0
                if tweet.public_metrics:
                    reply_count = tweet.public_metrics.get("reply_count", 0)
                
                if reply_count > 0 and reply_count < 100:
                    try:
                        replies_paginator = tweepy.Paginator(
                            client.search_recent_tweets,
                            query=f"conversation_id:{tweet.id}",
                            max_results=min(100, reply_count),
                            tweet_fields=["id", "text", "created_at", "author_id"],
                        )
                        
                        replies = []
                        for replies_page in replies_paginator:
                            if replies_page.data:
                                for reply in replies_page.data:
                                    if reply.id != tweet.id:
                                        replies.append({
                                            "id": reply.id,
                                            "text": reply.text,
                                            "created_at": reply.created_at.isoformat() if reply.created_at else None,
                                            "author_id": reply.author_id,
                                        })
                        
                        if replies:
                            tweet_data["replies"] = replies[:100]
                    except Exception as e:
                        # Search might not be available or might fail - that's okay
                        print(f"Note: Could not fetch replies for bookmark {tweet.id}: {e}")
                
                # Save individual bookmark JSON
                bookmark_file = backup_path / f"{tweet.id}.json"
                with open(bookmark_file, "w") as f:
                    json.dump(tweet_data, f, indent=2, sort_keys=True)
                
                downloaded_bookmarks.append({
                    "id": tweet.id,
                    "date": tweet_data["created_at"],
                    "text_preview": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                    "media_count": len(media_files),
                    "author_id": tweet.author_id,
                })
                
                bookmark_count += 1
                print(f"Downloaded bookmark {bookmark_count}: {tweet.id}")
                
            except Exception as e:
                print(f"Error processing bookmark {tweet.id}: {e}")
                continue
    
    # Save metadata summary
    metadata_file = backup_path / "bookmarks_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "username": username,
            "user_id": user_id,
            "total_bookmarks_downloaded": bookmark_count,
            "snapshot_date": snapshot_date.isoformat(),
            "bookmarks": downloaded_bookmarks,
        }, f, indent=2, sort_keys=True)
    
    print(f"Downloaded {bookmark_count} bookmarks to {backup_path}")
    
    return {
        "username": username,
        "bookmark_count": bookmark_count,
        "backup_path": str(backup_path),
        "bookmarks": downloaded_bookmarks,
    }


@task(cache_policy=NO_CACHE)
def download_likes(
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    username: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    local_backup_dir: Path = Path("./backups/local"),
    max_likes: Optional[int] = None,
) -> dict:
    """
    Download all liked tweets from the authenticated user's profile up to a snapshot date.

    Args:
        bearer_token: Twitter Bearer Token (for OAuth 2.0)
        api_key: Twitter API Key (for OAuth 1.0a)
        api_secret: Twitter API Secret (for OAuth 1.0a)
        access_token: Twitter Access Token (for OAuth 1.0a)
        access_token_secret: Twitter Access Token Secret (for OAuth 1.0a)
        username: Twitter username (optional, will use authenticated user if not provided)
        snapshot_date: Only download tweets created before or on this date (UTC)
        local_backup_dir: Base directory for backups
        max_likes: Maximum number of likes to download (None for all)

    Returns:
        Dictionary with download statistics
    """
    # Initialize Twitter API client
    if bearer_token:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
    elif api_key and api_secret and access_token and access_token_secret:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True,
        )
    else:
        raise ValueError(
            "Either bearer_token or (api_key, api_secret, access_token, access_token_secret) must be provided"
        )
    
    # Get user ID
    if username:
        user = client.get_user(username=username)
    else:
        user = client.get_me()
    
    if not user.data:
        raise ValueError(f"User not found: {username if username else 'authenticated user'}")
    
    user_id = user.data.id
    username = user.data.username
    
    # Create backup directory structure
    backup_path = local_backup_dir / "twitter" / username / "likes"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)
    
    # Download likes
    like_count = 0
    downloaded_likes = []
    
    print(f"Starting download of likes for @{username}...")
    
    # Get user's liked tweets
    tweet_fields = [
        "id", "text", "created_at", "author_id", "public_metrics",
        "attachments", "entities", "referenced_tweets"
    ]
    expansions = ["attachments.media_keys", "author_id"]
    media_fields = ["type", "url", "preview_image_url", "variants", "media_key"]
    
    paginator = tweepy.Paginator(
        client.get_liked_tweets,
        id=user_id,
        max_results=100,
        tweet_fields=tweet_fields,
        expansions=expansions,
        media_fields=media_fields,
        end_time=snapshot_date,
    )
    
    for page in paginator:
        if max_likes and like_count >= max_likes:
            break
        
        # Process likes in this page
        tweets = page.data or []
        includes = page.includes or {}
        media_dict = {}
        
        # Build media dictionary from includes
        if "media" in includes:
            for media in includes["media"]:
                media_dict[media.media_key] = media
        
        for tweet in tweets:
            if max_likes and like_count >= max_likes:
                break
            
            try:
                # Handle referenced_tweets properly
                referenced_tweets_data = None
                if hasattr(tweet, "referenced_tweets") and tweet.referenced_tweets:
                    referenced_tweets_data = [
                        {"type": rt.type, "id": rt.id} for rt in tweet.referenced_tweets
                    ]
                
                # Convert tweet to dict for JSON serialization
                tweet_data = {
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author_id": tweet.author_id,
                    "public_metrics": tweet.public_metrics,
                    "referenced_tweets": referenced_tweets_data,
                }
                
                # Get media attachments
                media_list = []
                if hasattr(tweet, "attachments") and tweet.attachments:
                    if hasattr(tweet.attachments, "media_keys") and tweet.attachments.media_keys:
                        for media_key in tweet.attachments.media_keys:
                            if media_key in media_dict:
                                media = media_dict[media_key]
                                media_info = {
                                    "type": media.type,
                                    "media_key": media_key,
                                }
                                
                                if media.type == "photo" and hasattr(media, "url"):
                                    media_info["url"] = media.url
                                elif media.type == "video":
                                    if hasattr(media, "variants") and media.variants:
                                        best_variant = max(
                                            [v for v in media.variants if hasattr(v, "bit_rate") and v.bit_rate],
                                            key=lambda v: v.bit_rate,
                                            default=None
                                        )
                                        if best_variant:
                                            media_info["url"] = best_variant.url
                                    if hasattr(media, "preview_image_url"):
                                        media_info["preview_image_url"] = media.preview_image_url
                                elif media.type == "animated_gif":
                                    if hasattr(media, "variants") and media.variants:
                                        media_info["url"] = media.variants[0].url
                                
                                media_list.append(media_info)
                
                # Download media files
                media_files = []
                for idx, media_info in enumerate(media_list):
                    if "url" in media_info:
                        ext = "jpg"
                        if media_info["type"] == "video":
                            ext = "mp4"
                        elif media_info["type"] == "animated_gif":
                            ext = "gif"
                        
                        media_filename = f"{tweet.id}_{idx}.{ext}"
                        media_filepath = media_path / media_filename
                        
                        if download_media(media_info["url"], media_filepath):
                            media_files.append({
                                "filename": media_filename,
                                "type": media_info["type"],
                                "url": media_info["url"],
                            })
                
                tweet_data["media"] = media_files
                
                # Get replies/comments if < 100
                reply_count = 0
                if tweet.public_metrics:
                    reply_count = tweet.public_metrics.get("reply_count", 0)
                
                if reply_count > 0 and reply_count < 100:
                    try:
                        replies_paginator = tweepy.Paginator(
                            client.search_recent_tweets,
                            query=f"conversation_id:{tweet.id}",
                            max_results=min(100, reply_count),
                            tweet_fields=["id", "text", "created_at", "author_id"],
                        )
                        
                        replies = []
                        for replies_page in replies_paginator:
                            if replies_page.data:
                                for reply in replies_page.data:
                                    if reply.id != tweet.id:
                                        replies.append({
                                            "id": reply.id,
                                            "text": reply.text,
                                            "created_at": reply.created_at.isoformat() if reply.created_at else None,
                                            "author_id": reply.author_id,
                                        })
                        
                        if replies:
                            tweet_data["replies"] = replies[:100]
                    except Exception as e:
                        # Search might not be available or might fail - that's okay
                        print(f"Note: Could not fetch replies for liked tweet {tweet.id}: {e}")
                
                # Save individual like JSON
                like_file = backup_path / f"{tweet.id}.json"
                with open(like_file, "w") as f:
                    json.dump(tweet_data, f, indent=2, sort_keys=True)
                
                downloaded_likes.append({
                    "id": tweet.id,
                    "date": tweet_data["created_at"],
                    "text_preview": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                    "media_count": len(media_files),
                    "author_id": tweet.author_id,
                })
                
                like_count += 1
                print(f"Downloaded like {like_count}: {tweet.id}")
                
            except Exception as e:
                print(f"Error processing liked tweet {tweet.id}: {e}")
                continue
    
    # Save metadata summary
    metadata_file = backup_path / "likes_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump({
            "username": username,
            "user_id": user_id,
            "total_likes_downloaded": like_count,
            "snapshot_date": snapshot_date.isoformat(),
            "likes": downloaded_likes,
        }, f, indent=2, sort_keys=True)
    
    print(f"Downloaded {like_count} likes to {backup_path}")
    
    return {
        "username": username,
        "like_count": like_count,
        "backup_path": str(backup_path),
        "likes": downloaded_likes,
    }


@flow()
def backup_twitter(
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    username: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    download_tweets: bool = True,
    download_bookmarks: bool = True,
    download_likes: bool = True,
    max_tweets: Optional[int] = None,
    max_bookmarks: Optional[int] = None,
    max_likes: Optional[int] = None,
    local_backup_dir: Path = Path("./backups/local"),
):
    """
    Main flow to backup Twitter/X posts, bookmarks, and likes up to a snapshot date.

    Args:
        bearer_token: Twitter Bearer Token (for OAuth 2.0)
        api_key: Twitter API Key (for OAuth 1.0a)
        api_secret: Twitter API Secret (for OAuth 1.0a)
        access_token: Twitter Access Token (for OAuth 1.0a)
        access_token_secret: Twitter Access Token Secret (for OAuth 1.0a)
        username: Twitter username (optional, will use authenticated user if not provided)
        snapshot_date: Only download tweets created before or on this date (UTC). Defaults to current time.
        download_tweets: Whether to download user's own tweets
        download_bookmarks: Whether to download bookmarked tweets
        download_likes: Whether to download liked tweets
        max_tweets: Maximum number of tweets to download (None for all)
        max_bookmarks: Maximum number of bookmarks to download (None for all)
        max_likes: Maximum number of likes to download (None for all)
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
    
    if download_tweets:
        print(f"Backing up tweets...")
        tweets_result = download_user_tweets(
            bearer_token=bearer_token,
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_tweets=max_tweets,
        )
        results["tweets"] = tweets_result
    
    if download_bookmarks:
        print(f"Backing up bookmarks...")
        bookmarks_result = download_bookmarks(
            bearer_token=bearer_token,
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_bookmarks=max_bookmarks,
        )
        results["bookmarks"] = bookmarks_result
    
    if download_likes:
        print(f"Backing up likes...")
        likes_result = download_likes(
            bearer_token=bearer_token,
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_likes=max_likes,
        )
        results["likes"] = likes_result
    
    username = results.get("tweets", results.get("bookmarks", results.get("likes", {}))).get("username", "unknown")
    print(f"Twitter backup completed for @{username}")
    print(f"  - Tweets downloaded: {results.get('tweets', {}).get('tweet_count', 0)}")
    print(f"  - Bookmarks downloaded: {results.get('bookmarks', {}).get('bookmark_count', 0)}")
    print(f"  - Likes downloaded: {results.get('likes', {}).get('like_count', 0)}")
    
    return results


if __name__ == "__main__":
    # Example usage - you can modify these parameters
    # You can get these credentials from https://developer.twitter.com/
    backup_twitter(
        bearer_token=None,  # Or set your Bearer Token
        api_key=None,  # Set your API Key
        api_secret=None,  # Set your API Secret
        access_token=None,  # Set your Access Token
        access_token_secret=None,  # Set your Access Token Secret
        username=None,  # Optional: specify username, or None to use authenticated user
        download_tweets=True,
        download_bookmarks=True,
        download_likes=True,
        max_tweets=None,  # Set to a number to limit tweets, or None for all
        max_bookmarks=None,  # Set to a number to limit bookmarks, or None for all
        max_likes=None,  # Set to a number to limit likes, or None for all
    )

