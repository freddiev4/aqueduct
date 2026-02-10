"""
Discord Server Message Backup Workflow

Downloads messages from Discord servers (guilds) that the bot is a member of.
Supports:
- All text channels in guilds
- Message content, attachments, embeds, reactions
- Media downloads (images, videos, files)
- Idempotent backups using snapshot_date
- Graceful degradation (continue on channel failures)

Requirements:
- requests library for Discord HTTP API
- Valid Discord bot token with Message Content intent enabled

Authentication:
1. Create a Discord bot at https://discord.com/developers/applications
2. Enable "Message Content Intent" under Bot > Privileged Gateway Intents
3. Invite bot to servers with VIEW_CHANNEL and READ_MESSAGE_HISTORY permissions
4. Copy bot token

All timestamps are stored in UTC timezone for consistency.
"""

import json
import re
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

from blocks.discord_block import DiscordBlock


BACKUP_DIR = Path("./backups/local/discord")
DISCORD_API_BASE = "https://discord.com/api/v10"


def sanitize_name(name: str) -> str:
    """
    Sanitize a string to be used as a directory/file name.
    Removes or replaces special characters that are problematic for filesystems.

    Args:
        name: Original name

    Returns:
        Sanitized name safe for filesystem use
    """
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    # Remove or replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Remove leading/trailing dots and spaces
    name = name.strip(". ")
    # Limit length to avoid filesystem issues
    if len(name) > 100:
        name = name[:100]
    return name or "unnamed"


@task(cache_policy=NO_CACHE)
def create_discord_session(bot_token: str) -> dict:
    """
    Create Discord API session headers.

    Args:
        bot_token: Discord bot token

    Returns:
        Dictionary with authorization headers
    """
    return {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }


@task(cache_policy=NO_CACHE)
def discord_api_request(
    endpoint: str,
    headers: dict,
    params: dict = None,
    max_retries: int = 5,
) -> dict:
    """
    Make a request to Discord API with rate limit handling.
    Implements exponential backoff for rate limits.

    Args:
        endpoint: API endpoint (e.g., "/users/@me/guilds")
        headers: Request headers with authorization
        params: Optional query parameters
        max_retries: Maximum number of retry attempts

    Returns:
        JSON response data

    Raises:
        RuntimeError: If request fails after all retries
    """
    logger = get_run_logger()
    url = f"{DISCORD_API_BASE}{endpoint}"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 5)
                logger.warning(
                    f"Rate limited. Retrying after {retry_after} seconds "
                    f"(attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(retry_after)
                continue

            # Handle other errors
            if response.status_code >= 400:
                logger.error(
                    f"Discord API error {response.status_code}: {response.text}"
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(
                        f"Discord API request failed: {response.status_code} {response.text}"
                    )

            # Success
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(
                    f"Request exception: {e}. Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                continue
            else:
                raise RuntimeError(f"Discord API request failed: {e}")

    raise RuntimeError(f"Failed to complete request after {max_retries} attempts")


@task(cache_policy=NO_CACHE)
def fetch_guilds(headers: dict) -> list[dict]:
    """
    Fetch all guilds (servers) the bot is a member of.
    Returns list sorted by guild ID for deterministic ordering.

    Args:
        headers: Discord API headers with authorization

    Returns:
        List of guild dictionaries
    """
    logger = get_run_logger()

    logger.info("Fetching guilds...")
    guilds = discord_api_request("/users/@me/guilds", headers)

    # Sort by guild ID for deterministic ordering
    guilds.sort(key=lambda g: g["id"])

    logger.info(f"Found {len(guilds)} guilds")
    return guilds


@task(cache_policy=NO_CACHE)
def fetch_text_channels(guild_id: str, headers: dict) -> list[dict]:
    """
    Fetch all text channels in a guild.
    Returns only text channels (type 0) sorted by channel ID.

    Args:
        guild_id: Discord guild ID
        headers: Discord API headers with authorization

    Returns:
        List of text channel dictionaries
    """
    logger = get_run_logger()

    logger.info(f"Fetching channels for guild {guild_id}...")
    channels = discord_api_request(f"/guilds/{guild_id}/channels", headers)

    # Filter for text channels (type 0) and announcement channels (type 5)
    # Type 0 = GUILD_TEXT, Type 5 = GUILD_ANNOUNCEMENT
    text_channels = [
        ch for ch in channels
        if ch.get("type") in [0, 5]
    ]

    # Sort by channel ID for deterministic ordering
    text_channels.sort(key=lambda c: c["id"])

    logger.info(f"Found {len(text_channels)} text channels in guild {guild_id}")
    return text_channels


@task(cache_policy=NO_CACHE)
def fetch_channel_messages(
    channel_id: str,
    channel_name: str,
    headers: dict,
    snapshot_date: datetime,
    max_messages: Optional[int] = None,
) -> list[dict]:
    """
    Fetch messages from a text channel with pagination, filtered by snapshot_date.
    Returns messages sorted by message ID (snowflake = chronological).

    For idempotency: Only includes messages with timestamp <= snapshot_date.
    This ensures running the workflow multiple times with the same snapshot_date
    produces identical results, regardless of when it's executed.

    Args:
        channel_id: Discord channel ID
        channel_name: Channel name (for logging)
        headers: Discord API headers with authorization
        snapshot_date: Only include messages at or before this timestamp (UTC)
        max_messages: Optional limit on number of messages to fetch

    Returns:
        List of message dictionaries
    """
    logger = get_run_logger()

    # Ensure snapshot_date is UTC-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    logger.info(f"Fetching messages from #{channel_name} (snapshot_date={snapshot_date.isoformat()}, limit={max_messages or 'all'})...")

    all_messages = []
    before_id = None
    messages_after_snapshot = 0

    while True:
        # Discord API limits to 100 messages per request
        params = {"limit": 100}
        if before_id:
            params["before"] = before_id

        try:
            messages = discord_api_request(
                f"/channels/{channel_id}/messages",
                headers,
                params=params,
            )
        except RuntimeError as e:
            logger.error(f"Failed to fetch messages from #{channel_name}: {e}")
            # Return what we've collected so far
            break

        if not messages:
            # No more messages
            break

        # Process and filter messages by snapshot_date
        for msg in messages:
            if msg.get("timestamp"):
                # Discord timestamps are in ISO format with 'Z' suffix (UTC)
                # Parse to datetime for comparison
                try:
                    msg_timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    # If parsing fails, skip this message
                    logger.warning(f"Failed to parse timestamp for message {msg.get('id')}: {msg.get('timestamp')}")
                    continue

                # IDEMPOTENCY: Skip messages after snapshot_date
                if msg_timestamp > snapshot_date:
                    messages_after_snapshot += 1
                    continue

                # Store UTC timestamp
                msg["timestamp_utc"] = msg["timestamp"]
            else:
                # No timestamp, skip message
                continue

            if msg.get("edited_timestamp") and msg["edited_timestamp"]:
                msg["edited_timestamp_utc"] = msg["edited_timestamp"]

            all_messages.append(msg)

        # Check if we've hit the limit
        if max_messages and len(all_messages) >= max_messages:
            all_messages = all_messages[:max_messages]
            logger.info(f"Reached message limit for #{channel_name}")
            break

        # Get the ID of the oldest message for pagination
        if messages:
            before_id = messages[-1]["id"]

        logger.debug(f"Fetched {len(all_messages)} messages so far from #{channel_name} (skipped {messages_after_snapshot} after snapshot)...")

        # Small delay to respect rate limits
        time.sleep(0.5)

    # Sort by message ID (snowflake IDs are chronologically ordered)
    all_messages.sort(key=lambda m: m["id"])

    if messages_after_snapshot > 0:
        logger.info(f"Filtered out {messages_after_snapshot} messages after snapshot_date")

    logger.info(f"Fetched {len(all_messages)} total messages from #{channel_name} (at or before {snapshot_date.isoformat()})")
    return all_messages


@task(cache_policy=NO_CACHE)
def download_attachment(
    attachment: dict,
    media_dir: Path,
    message_id: str,
    attachment_index: int,
) -> Optional[Path]:
    """
    Download a message attachment (image, video, file).

    Args:
        attachment: Attachment dictionary from Discord API
        media_dir: Directory to save media files
        message_id: Message ID (for unique filename)
        attachment_index: Index of attachment in message

    Returns:
        Path to downloaded file, or None if download failed
    """
    logger = get_run_logger()

    attachment_url = attachment.get("url")
    if not attachment_url:
        return None

    # Determine file extension from URL or filename
    filename = attachment.get("filename", "")
    if filename:
        file_ext = Path(filename).suffix
    else:
        parsed_url = urlparse(attachment_url)
        file_ext = Path(parsed_url.path).suffix or ".bin"

    # Create filename using message ID and attachment index
    media_filename = f"{message_id}_{attachment_index}{file_ext}"
    media_path = media_dir / media_filename

    # Check if file already exists (idempotency)
    if media_path.exists():
        logger.debug(f"Attachment {media_path} already exists, skipping download...")
        return media_path

    try:
        # Download attachment
        response = requests.get(attachment_url, timeout=60)
        response.raise_for_status()

        # Save to disk
        media_dir.mkdir(parents=True, exist_ok=True)
        with open(media_path, "wb") as f:
            f.write(response.content)

        logger.debug(f"Downloaded attachment to {media_path}")
        return media_path

    except Exception as e:
        logger.error(f"Failed to download attachment from {attachment_url}: {e}")
        return None


@task(cache_policy=NO_CACHE)
def save_channel_messages(
    guild_id: str,
    guild_name: str,
    channel_id: str,
    channel_name: str,
    messages: list[dict],
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
    download_media: bool = True,
) -> dict:
    """
    Save channel messages to disk with media downloads.

    Args:
        guild_id: Discord guild ID
        guild_name: Guild name (for directory structure)
        channel_id: Discord channel ID
        channel_name: Channel name (for directory structure)
        messages: List of message dictionaries
        snapshot_date: Date for this backup snapshot (UTC)
        output_dir: Base backup directory
        download_media: Whether to download attachments

    Returns:
        Dictionary with save statistics
    """
    logger = get_run_logger()

    # Ensure snapshot_date is UTC-aware
    if snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    # Sanitize names for filesystem
    safe_guild_name = sanitize_name(guild_name)
    safe_channel_name = sanitize_name(channel_name)

    # Create directory structure: discord/{guild_id}_{guild_name}/messages/{snapshot_date}/{channel_name}/
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    channel_dir = (
        output_dir
        / f"{guild_id}_{safe_guild_name}"
        / "messages"
        / snapshot_str
        / safe_channel_name
    )
    channel_dir.mkdir(parents=True, exist_ok=True)

    # Check if messages file already exists (idempotency)
    messages_file = channel_dir / "messages.json"
    if messages_file.exists():
        logger.info(f"Messages file already exists at {messages_file}, skipping save...")
        with open(messages_file, "r") as f:
            existing_data = json.load(f)
        return {
            "messages_saved": len(existing_data.get("messages", [])),
            "messages_file": str(messages_file),
            "already_existed": True,
            "attachments_downloaded": 0,
        }

    # Download attachments if requested
    attachments_downloaded = 0
    if download_media:
        media_dir = channel_dir / "media"
        for message in messages:
            attachments = message.get("attachments", [])
            for idx, attachment in enumerate(attachments):
                if download_attachment(
                    attachment,
                    media_dir,
                    message["id"],
                    idx,
                ):
                    attachments_downloaded += 1

    # Save all messages to a single JSON file
    messages_data = {
        "snapshot_date": snapshot_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "message_count": len(messages),
        "messages": messages,
    }

    with open(messages_file, "w") as f:
        json.dump(messages_data, f, indent=2, sort_keys=True)

    logger.info(f"Saved {len(messages)} messages to {messages_file}")

    return {
        "messages_saved": len(messages),
        "messages_file": str(messages_file),
        "attachments_downloaded": attachments_downloaded,
        "already_existed": False,
    }


@task()
def process_guild(
    guild: dict,
    headers: dict,
    snapshot_date: datetime,
    max_messages_per_channel: Optional[int],
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Process a single guild: fetch channels, messages, and save to disk.
    Implements graceful degradation (continue on channel failures).

    Args:
        guild: Guild dictionary from Discord API
        headers: Discord API headers with authorization
        snapshot_date: Date for this backup snapshot
        max_messages_per_channel: Optional limit on messages per channel
        output_dir: Base backup directory

    Returns:
        Dictionary with guild processing statistics
    """
    logger = get_run_logger()

    guild_id = guild["id"]
    guild_name = guild["name"]

    logger.info(f"Processing guild: {guild_name} ({guild_id})")

    # Fetch text channels
    try:
        channels = fetch_text_channels(guild_id, headers)
    except Exception as e:
        logger.error(f"Failed to fetch channels for guild {guild_name}: {e}")
        return {
            "guild_id": guild_id,
            "guild_name": guild_name,
            "success": False,
            "error": str(e),
            "channels_processed": 0,
        }

    if not channels:
        logger.warning(f"No text channels found in guild {guild_name}")
        return {
            "guild_id": guild_id,
            "guild_name": guild_name,
            "success": True,
            "channels_processed": 0,
            "total_messages": 0,
            "total_attachments": 0,
        }

    # Process each channel
    channels_processed = 0
    total_messages = 0
    total_attachments = 0
    failed_channels = []

    for channel in channels:
        channel_id = channel["id"]
        channel_name = channel["name"]

        try:
            # Fetch messages (filtered by snapshot_date for idempotency)
            messages = fetch_channel_messages(
                channel_id,
                channel_name,
                headers,
                snapshot_date=snapshot_date,
                max_messages=max_messages_per_channel,
            )

            if not messages:
                logger.info(f"No messages in #{channel_name}, skipping...")
                continue

            # Save messages
            save_result = save_channel_messages(
                guild_id=guild_id,
                guild_name=guild_name,
                channel_id=channel_id,
                channel_name=channel_name,
                messages=messages,
                snapshot_date=snapshot_date,
                output_dir=output_dir,
                download_media=True,
            )

            channels_processed += 1
            total_messages += save_result["messages_saved"]
            total_attachments += save_result["attachments_downloaded"]

        except Exception as e:
            # Graceful degradation: log error and continue with next channel
            logger.error(f"Failed to process channel #{channel_name} in {guild_name}: {e}")
            failed_channels.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "error": str(e),
            })
            continue

    logger.info(
        f"Processed {channels_processed}/{len(channels)} channels in {guild_name}"
    )

    return {
        "guild_id": guild_id,
        "guild_name": guild_name,
        "success": True,
        "channels_total": len(channels),
        "channels_processed": channels_processed,
        "channels_failed": len(failed_channels),
        "failed_channels": failed_channels,
        "total_messages": total_messages,
        "total_attachments": total_attachments,
    }


@task()
def check_snapshot_exists(
    guild_id: str,
    guild_name: str,
    snapshot_date: datetime,
    output_dir: Path = BACKUP_DIR,
) -> bool:
    """
    Check if a snapshot already exists for the given guild and date.
    Returns True if the snapshot directory and manifest exist.
    """
    logger = get_run_logger()

    safe_guild_name = sanitize_name(guild_name)
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    snapshot_dir = (
        output_dir
        / f"{guild_id}_{safe_guild_name}"
        / "messages"
        / snapshot_str
    )
    manifest_path = (
        output_dir
        / f"{guild_id}_{safe_guild_name}"
        / f"backup_manifest_{snapshot_str}.json"
    )

    if snapshot_dir.exists() and manifest_path.exists():
        logger.info(
            f"Snapshot for guild {guild_name} on {snapshot_str} already exists"
        )
        return True
    return False


@task()
def save_backup_manifest(
    guild_results: list[dict],
    snapshot_date: datetime,
    workflow_start: float,
    output_dir: Path = BACKUP_DIR,
) -> list[Path]:
    """
    Save manifest files for each guild with backup metadata.

    Args:
        guild_results: List of guild processing results
        snapshot_date: Date for this backup snapshot
        workflow_start: Workflow start timestamp
        output_dir: Base backup directory

    Returns:
        List of paths to manifest files
    """
    logger = get_run_logger()

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    manifest_paths = []

    for result in guild_results:
        if not result.get("success"):
            continue

        guild_id = result["guild_id"]
        guild_name = result["guild_name"]
        safe_guild_name = sanitize_name(guild_name)

        manifest_path = (
            output_dir
            / f"{guild_id}_{safe_guild_name}"
            / f"backup_manifest_{snapshot_str}.json"
        )

        manifest = {
            "snapshot_date": snapshot_date.isoformat(),
            "snapshot_date_str": snapshot_str,
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "workflow_version": "1.0.0",
            "python_version": sys.version,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "channels_total": result.get("channels_total", 0),
            "channels_processed": result.get("channels_processed", 0),
            "channels_failed": result.get("channels_failed", 0),
            "failed_channels": result.get("failed_channels", []),
            "total_messages": result.get("total_messages", 0),
            "total_attachments": result.get("total_attachments", 0),
            "processing_duration_seconds": time.time() - workflow_start,
        }

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)

        logger.info(f"Saved manifest to {manifest_path}")
        manifest_paths.append(manifest_path)

    return manifest_paths


@flow(name="backup-discord-messages")
def backup_discord_messages(
    snapshot_date: datetime,
    credentials_block_name: str = "discord-credentials",
    guild_ids: Optional[list[str]] = None,
    max_messages_per_channel: Optional[int] = None,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Main flow to backup Discord server messages.

    Args:
        snapshot_date: Date for this backup snapshot (for idempotency, UTC)
        credentials_block_name: Name of the Prefect Discord credentials block
        guild_ids: Optional list of guild IDs to backup (None = all guilds)
        max_messages_per_channel: Optional limit on messages per channel (None = all)
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
        f"Starting Discord backup (snapshot date: {snapshot_date.isoformat()})"
    )

    # Load credentials
    logger.info(f"Loading Discord credentials from block: {credentials_block_name}")
    discord_credentials = DiscordBlock.load(credentials_block_name)
    bot_token = discord_credentials.bot_token.get_secret_value()

    # Create API session
    headers = create_discord_session(bot_token)

    # Fetch guilds
    try:
        guilds = fetch_guilds(headers)
    except Exception as e:
        logger.error(f"Failed to fetch guilds: {e}")
        return {
            "success": False,
            "error": str(e),
            "snapshot_date": snapshot_date.isoformat(),
        }

    if not guilds:
        logger.warning("Bot is not a member of any guilds")
        return {
            "success": True,
            "guilds_processed": 0,
            "message": "No guilds found",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Filter guilds if specific IDs provided
    if guild_ids:
        guilds = [g for g in guilds if g["id"] in guild_ids]
        logger.info(f"Filtered to {len(guilds)} specified guilds")

    if not guilds:
        logger.warning("No guilds match the specified guild_ids")
        return {
            "success": True,
            "guilds_processed": 0,
            "message": "No matching guilds found",
            "snapshot_date": snapshot_date.isoformat(),
        }

    # Process each guild
    guild_results = []

    for guild in guilds:
        guild_id = guild["id"]
        guild_name = guild["name"]

        # Check if snapshot already exists (idempotency)
        if check_snapshot_exists(guild_id, guild_name, snapshot_date, output_dir):
            logger.info(
                f"Snapshot for guild {guild_name} already exists. Skipping."
            )
            guild_results.append({
                "guild_id": guild_id,
                "guild_name": guild_name,
                "success": True,
                "skipped": True,
                "message": "Snapshot already exists",
            })
            continue

        # Process guild
        try:
            result = process_guild(
                guild=guild,
                headers=headers,
                snapshot_date=snapshot_date,
                max_messages_per_channel=max_messages_per_channel,
                output_dir=output_dir,
            )
            guild_results.append(result)

        except Exception as e:
            # Graceful degradation: log error and continue with next guild
            logger.error(f"Failed to process guild {guild_name}: {e}")
            guild_results.append({
                "guild_id": guild_id,
                "guild_name": guild_name,
                "success": False,
                "error": str(e),
            })
            continue

    # Save manifests
    manifest_paths = save_backup_manifest(
        guild_results=guild_results,
        snapshot_date=snapshot_date,
        workflow_start=workflow_start,
        output_dir=output_dir,
    )

    # Compute summary statistics
    successful_guilds = [r for r in guild_results if r.get("success")]
    failed_guilds = [r for r in guild_results if not r.get("success")]
    total_messages = sum(r.get("total_messages", 0) for r in successful_guilds)
    total_attachments = sum(r.get("total_attachments", 0) for r in successful_guilds)

    logger.info(
        f"Successfully backed up {len(successful_guilds)}/{len(guilds)} guilds"
    )
    logger.info(f"Total messages: {total_messages}")
    logger.info(f"Total attachments: {total_attachments}")

    if failed_guilds:
        logger.warning(
            f"Failed to backup {len(failed_guilds)} guilds: "
            f"{[g['guild_name'] for g in failed_guilds]}"
        )

    return {
        "success": True,
        "snapshot_date": snapshot_date.isoformat(),
        "guilds_total": len(guilds),
        "guilds_processed": len(successful_guilds),
        "guilds_failed": len(failed_guilds),
        "total_messages": total_messages,
        "total_attachments": total_attachments,
        "processing_duration_seconds": time.time() - workflow_start,
        "manifest_paths": [str(p) for p in manifest_paths],
        "guild_results": guild_results,
    }


if __name__ == "__main__":
    # Example usage - backup all guilds
    backup_discord_messages(
        snapshot_date=datetime.now(timezone.utc),
        guild_ids=None,  # None = all guilds, or provide list like ["123456789", "987654321"]
        max_messages_per_channel=100,  # Limit for testing, set to None for full backup
    )
