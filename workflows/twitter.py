import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from xdk import Client


# X API v2 field configurations
TWEET_FIELDS = [
    "id", "text", "created_at", "author_id", "public_metrics",
    "attachments", "entities", "referenced_tweets", "in_reply_to_user_id",
    "conversation_id",
]
EXPANSIONS = ["attachments.media_keys", "author_id"]
MEDIA_FIELDS = ["type", "url", "preview_image_url", "variants", "media_key"]


def download_media_file(url: str, filepath: Path) -> bool:
    """Download media (image/video) from URL to filepath."""
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


def _create_client(
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
) -> Client:
    """Create an X API client with the appropriate auth method.

    OAuth 1.0a (api_key + access_token) is preferred for user-context
    operations like bookmarks and likes. Bearer token works for public
    read-only endpoints like user timeline and search.
    """
    if api_key and api_secret and access_token and access_token_secret:
        return Client(
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
    if bearer_token:
        return Client(bearer_token=bearer_token)
    raise ValueError(
        "Provide either (api_key, api_secret, access_token, access_token_secret) "
        "for full access, or bearer_token for read-only public access."
    )


def _get_user_info(client: Client, username: Optional[str] = None) -> tuple[str, str]:
    """Return (user_id, username) for the target user."""
    if username:
        resp = client.users.get_by_usernames(
            usernames=[username],
            user_fields=["id", "username"],
        )
        users = getattr(resp, "data", None)
        if not users:
            raise ValueError(f"User not found: {username}")
        user = users[0]
        return str(user["id"]), user["username"]

    resp = client.users.get_me(user_fields=["id", "username"])
    user = getattr(resp, "data", None)
    if not user:
        raise ValueError("Could not retrieve authenticated user")
    return str(user["id"]), user["username"]


def _build_media_lookup(page) -> dict:
    """Build a {media_key: media_dict} lookup from the page includes."""
    includes = getattr(page, "includes", None) or {}
    if isinstance(includes, dict):
        media_items = includes.get("media", [])
    else:
        media_items = getattr(includes, "media", []) or []

    lookup = {}
    for m in media_items:
        key = m.get("media_key") if isinstance(m, dict) else getattr(m, "media_key", None)
        if key:
            lookup[key] = m
    return lookup


def _best_media_url(media: dict) -> Optional[str]:
    """Extract the best download URL from a media object."""
    mtype = media.get("type", "")

    if mtype == "photo":
        return media.get("url")

    if mtype == "video":
        best_url, best_br = None, 0
        for v in media.get("variants", []):
            if v.get("content_type") == "video/mp4":
                br = v.get("bit_rate", 0) or 0
                if br > best_br:
                    best_br, best_url = br, v.get("url")
        return best_url

    if mtype == "animated_gif":
        variants = media.get("variants", [])
        return variants[0].get("url") if variants else None

    return None


def _download_tweet_media(tweet: dict, media_lookup: dict, media_path: Path) -> list[dict]:
    """Download all media for a tweet. Returns list of saved file info dicts."""
    attachments = tweet.get("attachments") or {}
    media_keys = attachments.get("media_keys", [])
    saved = []

    for idx, mk in enumerate(media_keys):
        media = media_lookup.get(mk)
        if not media:
            continue
        url = _best_media_url(media)
        if not url:
            continue

        mtype = media.get("type", "photo")
        ext = {"video": "mp4", "animated_gif": "gif"}.get(mtype, "jpg")
        filename = f"{tweet['id']}_{idx}.{ext}"
        filepath = media_path / filename

        if download_media_file(url, filepath):
            saved.append({"filename": filename, "type": mtype, "url": url})

    return saved


def _serialize_tweet(tweet: dict, media_files: list[dict]) -> dict:
    """Convert an API tweet dict to our storage format."""
    ref_tweets = tweet.get("referenced_tweets")
    if ref_tweets:
        ref_tweets = [{"type": r.get("type"), "id": r.get("id")} for r in ref_tweets]

    return {
        "id": tweet.get("id"),
        "text": tweet.get("text"),
        "created_at": tweet.get("created_at"),
        "author_id": tweet.get("author_id"),
        "public_metrics": tweet.get("public_metrics"),
        "referenced_tweets": ref_tweets,
        "in_reply_to_user_id": tweet.get("in_reply_to_user_id"),
        "media": media_files,
    }


def _fetch_replies(
    client: Client, tweet_id: str, snapshot_date: Optional[datetime] = None,
) -> list[dict]:
    """Fetch replies to a tweet via recent search. Returns list of reply dicts."""
    replies = []
    try:
        search_kwargs = dict(
            query=f"conversation_id:{tweet_id}",
            max_results=100,
            tweet_fields=["id", "text", "created_at", "author_id"],
        )
        if snapshot_date:
            search_kwargs["end_time"] = snapshot_date.isoformat()

        for page in client.posts.search_recent(**search_kwargs):
            page_data = getattr(page, "data", []) or []
            for r in page_data:
                if r.get("id") != tweet_id:
                    replies.append({
                        "id": r.get("id"),
                        "text": r.get("text"),
                        "created_at": r.get("created_at"),
                        "author_id": r.get("author_id"),
                    })
    except Exception as e:
        print(f"Note: Could not fetch replies for tweet {tweet_id}: {e}")
    # Sort by created_at for deterministic ordering across runs
    replies.sort(key=lambda x: x.get("created_at") or "")
    return replies[:100]


def _process_page(
    page,
    media_path: Path,
    backup_path: Path,
    client: Client,
    count: int,
    max_count: Optional[int],
    downloaded: list,
    label: str,
    fetch_replies: bool = False,
    snapshot_date: Optional[datetime] = None,
) -> int:
    """Process a single page of tweets/bookmarks/likes. Returns updated count."""
    page_data = getattr(page, "data", []) or []
    media_lookup = _build_media_lookup(page)

    for tweet in page_data:
        if max_count and count >= max_count:
            break

        # Client-side temporal filter for endpoints that don't support
        # end_time (bookmarks, likes). Skip tweets created after snapshot.
        if snapshot_date and tweet.get("created_at"):
            try:
                created = datetime.fromisoformat(
                    tweet["created_at"].replace("Z", "+00:00")
                )
                if created > snapshot_date:
                    continue
            except (ValueError, TypeError):
                pass

        try:
            media_files = _download_tweet_media(tweet, media_lookup, media_path)
            tweet_data = _serialize_tweet(tweet, media_files)

            if fetch_replies:
                pm = tweet.get("public_metrics") or {}
                rc = pm.get("reply_count", 0)
                if 0 < rc < 100:
                    replies = _fetch_replies(client, tweet["id"], snapshot_date)
                    if replies:
                        tweet_data["replies"] = replies

            with open(backup_path / f"{tweet['id']}.json", "w") as f:
                json.dump(tweet_data, f, indent=2, sort_keys=True)

            text = tweet.get("text", "")
            downloaded.append({
                "id": tweet["id"],
                "date": tweet.get("created_at"),
                "text_preview": text[:100] + "..." if len(text) > 100 else text,
                "media_count": len(media_files),
                "author_id": tweet.get("author_id"),
            })

            count += 1
            print(f"Downloaded {label} {count}: {tweet['id']}")

        except Exception as e:
            print(f"Error processing {label} {tweet.get('id')}: {e}")
            continue

    return count


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
    """Download tweets from a user's timeline."""
    client = _create_client(bearer_token, api_key, api_secret, access_token, access_token_secret)
    user_id, username = _get_user_info(client, username)

    backup_path = local_backup_dir / "twitter" / username / "tweets"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting download of tweets for @{username}...")

    kwargs = dict(
        max_results=100,
        tweet_fields=TWEET_FIELDS,
        expansions=EXPANSIONS,
        media_fields=MEDIA_FIELDS,
    )
    if snapshot_date:
        kwargs["end_time"] = snapshot_date.isoformat()
    if not include_replies:
        kwargs["exclude"] = ["retweets"]

    tweet_count = 0
    downloaded_tweets = []

    for page in client.users.get_posts(user_id, **kwargs):
        if max_tweets and tweet_count >= max_tweets:
            break
        tweet_count = _process_page(
            page, media_path, backup_path, client,
            tweet_count, max_tweets, downloaded_tweets,
            label="tweet", fetch_replies=True,
            snapshot_date=snapshot_date,
        )

    # Sort by ID for deterministic metadata output across runs
    downloaded_tweets.sort(key=lambda x: x["id"])

    metadata = {
        "username": username,
        "user_id": user_id,
        "total_tweets_downloaded": tweet_count,
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "tweets": downloaded_tweets,
    }
    with open(backup_path / "tweets_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    print(f"Downloaded {tweet_count} tweets to {backup_path}")
    return {
        "username": username,
        "tweet_count": tweet_count,
        "backup_path": str(backup_path),
        "tweets": downloaded_tweets,
    }


@task(cache_policy=NO_CACHE)
def download_user_bookmarks(
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
    """Download bookmarked tweets for the authenticated user.

    Note: Bookmarks require user-context auth (OAuth 1.0a with api_key +
    access_token). Bearer token alone is not sufficient.
    """
    client = _create_client(bearer_token, api_key, api_secret, access_token, access_token_secret)
    user_id, username = _get_user_info(client, username)

    backup_path = local_backup_dir / "twitter" / username / "bookmarks"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting download of bookmarks for @{username}...")

    # Bookmarks endpoint does not support end_time server-side;
    # _process_page applies client-side filtering via snapshot_date.
    kwargs = dict(
        max_results=100,
        tweet_fields=TWEET_FIELDS,
        expansions=EXPANSIONS,
        media_fields=MEDIA_FIELDS,
    )

    bookmark_count = 0
    downloaded_bookmarks = []

    for page in client.users.get_bookmarks(user_id, **kwargs):
        if max_bookmarks and bookmark_count >= max_bookmarks:
            break
        bookmark_count = _process_page(
            page, media_path, backup_path, client,
            bookmark_count, max_bookmarks, downloaded_bookmarks,
            label="bookmark",
            snapshot_date=snapshot_date,
        )

    downloaded_bookmarks.sort(key=lambda x: x["id"])

    metadata = {
        "username": username,
        "user_id": user_id,
        "total_bookmarks_downloaded": bookmark_count,
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "bookmarks": downloaded_bookmarks,
    }
    with open(backup_path / "bookmarks_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    print(f"Downloaded {bookmark_count} bookmarks to {backup_path}")
    return {
        "username": username,
        "bookmark_count": bookmark_count,
        "backup_path": str(backup_path),
        "bookmarks": downloaded_bookmarks,
    }


@task(cache_policy=NO_CACHE)
def download_user_likes(
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
    """Download liked tweets for the authenticated user.

    Note: Likes require user-context auth (OAuth 1.0a with api_key +
    access_token). Bearer token alone is not sufficient.
    """
    client = _create_client(bearer_token, api_key, api_secret, access_token, access_token_secret)
    user_id, username = _get_user_info(client, username)

    backup_path = local_backup_dir / "twitter" / username / "likes"
    backup_path.mkdir(parents=True, exist_ok=True)
    media_path = backup_path / "media"
    media_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting download of likes for @{username}...")

    # Likes endpoint does not support end_time server-side;
    # _process_page applies client-side filtering via snapshot_date.
    kwargs = dict(
        max_results=100,
        tweet_fields=TWEET_FIELDS,
        expansions=EXPANSIONS,
        media_fields=MEDIA_FIELDS,
    )

    like_count = 0
    downloaded_likes = []

    for page in client.users.get_liked_posts(user_id, **kwargs):
        if max_likes and like_count >= max_likes:
            break
        like_count = _process_page(
            page, media_path, backup_path, client,
            like_count, max_likes, downloaded_likes,
            label="like",
            snapshot_date=snapshot_date,
        )

    downloaded_likes.sort(key=lambda x: x["id"])

    metadata = {
        "username": username,
        "user_id": user_id,
        "total_likes_downloaded": like_count,
        "snapshot_date": snapshot_date.isoformat() if snapshot_date else None,
        "likes": downloaded_likes,
    }
    with open(backup_path / "likes_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    print(f"Downloaded {like_count} likes to {backup_path}")
    return {
        "username": username,
        "like_count": like_count,
        "backup_path": str(backup_path),
        "likes": downloaded_likes,
    }


@flow()
def backup_twitter(
    credentials_block_name: str = "twitter-credentials",
    bearer_token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    username: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    include_tweets: bool = True,
    include_bookmarks: bool = True,
    include_likes: bool = True,
    max_tweets: Optional[int] = None,
    max_bookmarks: Optional[int] = None,
    max_likes: Optional[int] = None,
    local_backup_dir: Path = Path("./backups/local"),
):
    """Main flow to backup Twitter/X posts, bookmarks, and likes.

    Authentication (in order of precedence):
        1. Explicit params: pass api_key/api_secret/access_token/access_token_secret
           or bearer_token directly.
        2. Prefect Block: loads credentials from the named TwitterBlock
           (default: "twitter-credentials"). Register the block first by
           running: python blocks/twitter_block.py

    Get credentials from https://developer.x.com/
    """
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc)
    elif snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)
    elif snapshot_date.tzinfo != timezone.utc:
        snapshot_date = snapshot_date.astimezone(timezone.utc)

    # If no explicit creds provided, load from Prefect Block
    if not any([bearer_token, api_key, api_secret, access_token, access_token_secret]):
        from blocks.twitter_block import TwitterBlock

        print(f"Loading credentials from block: {credentials_block_name}")
        creds = TwitterBlock.load(credentials_block_name)
        bearer_token = creds.bearer_token.get_secret_value() if creds.bearer_token else None
        api_key = creds.api_key.get_secret_value() if creds.api_key else None
        api_secret = creds.api_secret.get_secret_value() if creds.api_secret else None
        access_token = creds.access_token.get_secret_value() if creds.access_token else None
        access_token_secret = creds.access_token_secret.get_secret_value() if creds.access_token_secret else None

    auth_kwargs = dict(
        bearer_token=bearer_token,
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    results = {}

    if include_tweets:
        print("Backing up tweets...")
        results["tweets"] = download_user_tweets(
            **auth_kwargs,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_tweets=max_tweets,
        )

    if include_bookmarks:
        print("Backing up bookmarks...")
        results["bookmarks"] = download_user_bookmarks(
            **auth_kwargs,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_bookmarks=max_bookmarks,
        )

    if include_likes:
        print("Backing up likes...")
        results["likes"] = download_user_likes(
            **auth_kwargs,
            username=username,
            snapshot_date=snapshot_date,
            local_backup_dir=local_backup_dir,
            max_likes=max_likes,
        )

    resolved_username = (
        results.get("tweets", results.get("bookmarks", results.get("likes", {})))
        .get("username", "unknown")
    )
    print(f"Twitter/X backup completed for @{resolved_username}")
    print(f"  Tweets: {results.get('tweets', {}).get('tweet_count', 0)}")
    print(f"  Bookmarks: {results.get('bookmarks', {}).get('bookmark_count', 0)}")
    print(f"  Likes: {results.get('likes', {}).get('like_count', 0)}")

    return results


if __name__ == "__main__":
    # Credentials are loaded from env vars if set, otherwise from the
    # "twitter-credentials" Prefect Block (register it first with:
    #   python blocks/twitter_block.py)
    backup_twitter(
        bearer_token=os.environ.get("X_BEARER_TOKEN"),
        api_key=os.environ.get("X_API_KEY"),
        api_secret=os.environ.get("X_API_SECRET"),
        access_token=os.environ.get("X_ACCESS_TOKEN"),
        access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET"),
    )
