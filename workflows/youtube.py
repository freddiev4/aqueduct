"""
YouTube Video Backup Workflow

Downloads YouTube videos using yt-dlp. Supports:
- Single video downloads (triggered via Twilio SMS webhook)
- Playlist downloads
- No authentication required (public videos only)

For Twilio integration, run the webhook server:
    python workflows/youtube.py --serve

Then configure Twilio to send SMS webhooks to:
    https://your-domain.com/sms (or use ngrok for local dev)
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


YOUTUBE_URL_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|shorts/)?([a-zA-Z0-9_-]{11})'
)

BACKUP_DIR = Path("./backups/local/youtube")


@task(cache_policy=NO_CACHE)
def extract_youtube_url(text: str) -> Optional[str]:
    """
    Extract a YouTube URL from text (e.g., SMS message body).
    Returns the full URL or None if no valid URL found.
    """
    logger = get_run_logger()

    match = YOUTUBE_URL_PATTERN.search(text)
    if match:
        video_id = match.group(5)
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"Extracted YouTube URL: {url}")
        return url

    logger.warning(f"No YouTube URL found in text: {text[:100]}...")
    return None


@task(cache_policy=NO_CACHE)
def get_video_info(url: str) -> dict:
    """
    Fetch video metadata without downloading.
    Returns video info dict with title, uploader, duration, etc.
    """
    logger = get_run_logger()

    if yt_dlp is None:
        raise ImportError("yt-dlp is not installed. Run: pip install yt-dlp")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_info = {
        'id': info.get('id'),
        'title': info.get('title'),
        'uploader': info.get('uploader'),
        'uploader_id': info.get('uploader_id'),
        'channel_id': info.get('channel_id'),
        'duration': info.get('duration'),
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'upload_date': info.get('upload_date'),
        'description': info.get('description'),
        'categories': info.get('categories'),
        'tags': info.get('tags'),
        'thumbnail': info.get('thumbnail'),
        'webpage_url': info.get('webpage_url'),
    }

    logger.info(f"Fetched info for: {video_info['title']} by {video_info['uploader']}")
    return video_info


@task(cache_policy=NO_CACHE)
def download_video(
    url: str,
    output_dir: Path,
    format_spec: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    download_archive: Optional[Path] = None,
) -> dict:
    """
    Download a YouTube video using yt-dlp.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the video
        format_spec: yt-dlp format specification (default: best up to 1080p)
        download_archive: Optional path to archive file for idempotency

    Returns:
        Dict with download result info
    """
    logger = get_run_logger()

    if yt_dlp is None:
        raise ImportError("yt-dlp is not installed. Run: pip install yt-dlp")

    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'format': format_spec,
        'merge_output_format': 'mp4',
        'outtmpl': str(output_dir / '%(uploader)s/%(title)s [%(id)s].%(ext)s'),
        'writeinfojson': True,
        'writethumbnail': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'ignoreerrors': False,
        'no_warnings': False,
        'quiet': False,
    }

    if download_archive:
        ydl_opts['download_archive'] = str(download_archive)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        result = {
            'success': True,
            'video_id': info.get('id'),
            'title': info.get('title'),
            'uploader': info.get('uploader'),
            'filename': ydl.prepare_filename(info),
            'duration': info.get('duration'),
            'filesize': info.get('filesize') or info.get('filesize_approx'),
        }

        logger.info(f"Successfully downloaded: {result['title']}")
        return result

    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return {
            'success': False,
            'url': url,
            'error': str(e),
        }


@task(cache_policy=NO_CACHE)
def save_download_record(
    video_info: dict,
    download_result: dict,
    trigger_source: str,
    output_dir: Path,
    snapshot_date: datetime,
) -> Path:
    """
    Save a record of the download for tracking purposes.
    Uses snapshot_date for idempotent filenames and timestamps.
    """
    logger = get_run_logger()

    records_dir = output_dir / "_records"
    records_dir.mkdir(parents=True, exist_ok=True)

    # Normalize snapshot_date to UTC midnight for consistency
    snapshot_normalized = snapshot_date.replace(hour=0, minute=0, second=0, microsecond=0)

    record = {
        'downloaded_at': snapshot_normalized.isoformat(),
        'trigger_source': trigger_source,
        'video_info': video_info,
        'download_result': download_result,
    }

    # Use date-only format for idempotent filenames (no time component)
    record_file = records_dir / f"{video_info['id']}_{snapshot_normalized.strftime('%Y%m%d')}.json"

    with open(record_file, 'w') as f:
        json.dump(record, f, indent=2, default=str, sort_keys=True)

    logger.info(f"Saved download record to {record_file}")
    return record_file


@flow(name="download-youtube-video")
def download_youtube_video(
    url: str,
    trigger_source: str = "manual",
    output_dir: Path = BACKUP_DIR,
    format_spec: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    snapshot_date: Optional[datetime] = None,
) -> dict:
    """
    Main flow to download a single YouTube video.

    Args:
        url: YouTube video URL
        trigger_source: Where the download was triggered from (e.g., "twilio", "manual")
        output_dir: Base directory for downloads
        format_spec: yt-dlp format specification
        snapshot_date: Date for this backup snapshot (defaults to current UTC date at midnight)

    Returns:
        Dict with video info and download result
    """
    logger = get_run_logger()
    logger.info(f"Starting YouTube download flow for: {url}")

    # Ensure output dir is a Path
    output_dir = Path(output_dir)

    # Default snapshot_date to current UTC date at midnight for idempotency
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    elif snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    logger.info(f"Using snapshot date: {snapshot_str}")

    # Get video info first
    video_info = get_video_info(url)

    # Download archive for idempotency (shared across all snapshots)
    download_archive = output_dir / "download_archive.txt"

    # Download the video to snapshot-dated directory
    download_result = download_video(
        url=url,
        output_dir=output_dir / snapshot_str / "videos",
        format_spec=format_spec,
        download_archive=download_archive,
    )

    # Save download record to snapshot-dated directory
    save_download_record(
        video_info=video_info,
        download_result=download_result,
        trigger_source=trigger_source,
        output_dir=output_dir / snapshot_str,
        snapshot_date=snapshot_date,
    )

    return {
        'video_info': video_info,
        'download_result': download_result,
        'snapshot_date': snapshot_str,
    }


@flow(name="download-youtube-from-sms")
def download_youtube_from_sms(
    sms_body: str,
    sms_from: str,
    output_dir: Path = BACKUP_DIR,
    snapshot_date: Optional[datetime] = None,
) -> dict:
    """
    Flow triggered by Twilio SMS webhook.
    Extracts YouTube URL from SMS body and downloads the video.

    Args:
        sms_body: The SMS message body
        sms_from: The sender's phone number
        output_dir: Base directory for downloads
        snapshot_date: Date for this backup snapshot (defaults to current UTC date at midnight)

    Returns:
        Dict with extraction and download results
    """
    logger = get_run_logger()
    logger.info(f"Received SMS from {sms_from}: {sms_body[:100]}...")

    # Extract YouTube URL from SMS
    url = extract_youtube_url(sms_body)

    if not url:
        logger.warning("No YouTube URL found in SMS")
        return {
            'success': False,
            'error': 'No YouTube URL found in message',
            'sms_from': sms_from,
            'sms_body': sms_body,
        }

    # Download the video
    result = download_youtube_video(
        url=url,
        trigger_source=f"twilio:{sms_from}",
        output_dir=output_dir,
        snapshot_date=snapshot_date,
    )

    result['sms_from'] = sms_from
    result['extracted_url'] = url

    return result


def create_twilio_webhook_app():
    """
    Create a Flask app for the Twilio SMS webhook.

    To run:
        python workflows/youtube.py --serve

    Configure Twilio webhook URL to point to:
        https://your-domain.com/sms
    """
    try:
        from flask import Flask, request
        from twilio.twiml.messaging_response import MessagingResponse
    except ImportError:
        raise ImportError(
            "Flask and Twilio are required for the webhook server. "
            "Run: pip install flask twilio"
        )

    app = Flask(__name__)

    @app.route("/sms", methods=['POST'])
    def sms_webhook():
        """Handle incoming SMS from Twilio."""
        sms_body = request.form.get('Body', '')
        sms_from = request.form.get('From', '')

        # Trigger the Prefect flow
        try:
            result = download_youtube_from_sms(
                sms_body=sms_body,
                sms_from=sms_from,
            )

            # Create TwiML response
            resp = MessagingResponse()

            if result.get('download_result', {}).get('success'):
                title = result.get('video_info', {}).get('title', 'Unknown')
                resp.message(f"Downloaded: {title}")
            else:
                error = result.get('error') or result.get('download_result', {}).get('error', 'Unknown error')
                resp.message(f"Failed: {error}")

            return str(resp)

        except Exception as e:
            resp = MessagingResponse()
            resp.message(f"Error: {str(e)[:100]}")
            return str(resp)

    @app.route("/health", methods=['GET'])
    def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "youtube-downloader"}

    return app


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        # Run the Twilio webhook server
        app = create_twilio_webhook_app()
        port = int(os.environ.get("PORT", 5000))
        print(f"Starting Twilio webhook server on port {port}")
        print(f"Configure Twilio to POST to: http://your-domain:{port}/sms")
        app.run(host="0.0.0.0", port=port, debug=True)
    else:
        # Manual test - download a sample video
        test_url = input("Enter YouTube URL to download: ").strip()
        if test_url:
            result = download_youtube_video(url=test_url, trigger_source="manual")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("No URL provided. Usage:")
            print("  python workflows/youtube.py          # Interactive download")
            print("  python workflows/youtube.py --serve  # Run Twilio webhook server")
