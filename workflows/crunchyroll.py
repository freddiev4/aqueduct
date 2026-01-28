"""
Crunchyroll Anime Backup Workflow

Downloads anime episodes from Crunchyroll using multi-downloader-nx.
Requires:
- multi-downloader-nx installed (see workflows/README.md for build instructions)
- ffmpeg installed
- MKVtoolNix installed (optional, for MKV output)
- Crunchyroll Premium subscription

Series configuration is stored in a JSON file that can be edited to add
new series or update episode ranges.

Authentication:
    Run `multi-downloader-nx --service crunchy --auth` to authenticate
    with your Crunchyroll account before downloading.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger


BACKUP_DIR = Path("./backups/local/crunchyroll")
CONFIG_FILE = Path("./config/crunchyroll_series.json")


def get_default_config() -> dict:
    """Return default configuration structure."""
    return {
        "version": "1.1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "crunchyroll_config": {
            "quality": "1080",
            "audio_lang": "jpn",
            "subtitle_lang": "en",
            "output_format": "mkv",
        },
        "series": [
            # Example entry:
            # {
            #     "name": "Solo Leveling S1",
            #     "season_id": "GR19CPDWM",  # Required: Season ID from Crunchyroll
            #     "episodes": "1-12",  # Episode range
            #     "enabled": True,
            #     "notes": "Use --series SERIES_ID to find season IDs"
            # }
        ]
    }


def extract_series_id_from_url(url: str) -> Optional[str]:
    """
    Extract series ID from a Crunchyroll URL.
    Example: https://www.crunchyroll.com/series/GDKHZEJ0K/solo-leveling -> GDKHZEJ0K
    """
    import re
    match = re.search(r'/series/([A-Z0-9]+)', url)
    return match.group(1) if match else None


@task(cache_policy=NO_CACHE)
def check_crunchyroll_auth() -> dict:
    """
    Check if user is authenticated with Crunchyroll.
    Returns auth status and username if authenticated.
    """
    logger = get_run_logger()

    multi_dl_cmd = find_multi_downloader_nx()

    # Run a simple command that shows auth status
    # Using --series with a known series ID to check auth
    try:
        result = subprocess.run(
            [multi_dl_cmd, "--service", "crunchy", "--series", "GDKHZEJ0K"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Check for anonymous user
        if "USER: Anonymous" in output:
            logger.warning("Not authenticated with Crunchyroll (Anonymous user)")
            return {
                'authenticated': False,
                'username': 'Anonymous',
                'message': 'Run: multi-downloader-nx --service crunchy --auth',
            }

        # Try to extract username
        import re
        user_match = re.search(r'USER:\s*(\S+)', output)
        username = user_match.group(1) if user_match else 'Unknown'

        logger.info(f"Authenticated as: {username}")
        return {
            'authenticated': True,
            'username': username,
        }

    except Exception as e:
        logger.error(f"Failed to check auth status: {e}")
        return {
            'authenticated': False,
            'error': str(e),
        }


@task(cache_policy=NO_CACHE)
def list_seasons_for_series(series_id: str) -> dict:
    """
    List available seasons for a series ID.
    Use this to find the season_id needed for downloads.

    Args:
        series_id: The series ID (e.g., GDKHZEJ0K for Solo Leveling)

    Returns:
        Dict with seasons info including season_ids
    """
    logger = get_run_logger()

    multi_dl_cmd = find_multi_downloader_nx()

    try:
        # Use --show-raw to get JSON data with season IDs
        result = subprocess.run(
            [multi_dl_cmd, "--service", "crunchy", "--show-raw", series_id],
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout + result.stderr

        # Parse JSON lines from output
        # Each line after the header is a JSON object for a season
        seasons = []
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('{') and '"id"' in line:
                try:
                    data = json.loads(line)
                    seasons.append({
                        'season_num': data.get('season_number'),
                        'season_id': data.get('id'),
                        'title': data.get('title'),
                        'episode_count': data.get('number_of_episodes'),
                        'is_dubbed': data.get('is_dubbed', False),
                        'is_subbed': data.get('is_subbed', False),
                        'audio_locales': data.get('audio_locales', []),
                    })
                except json.JSONDecodeError:
                    continue

        # Sort by season number
        seasons.sort(key=lambda x: x.get('season_num', 0))

        logger.info(f"Found {len(seasons)} seasons for series {series_id}")
        return {
            'series_id': series_id,
            'seasons': seasons,
        }

    except Exception as e:
        logger.error(f"Failed to list seasons: {e}")
        return {
            'series_id': series_id,
            'error': str(e),
        }


@task(cache_policy=NO_CACHE)
def load_series_config(config_path: Path = CONFIG_FILE, use_logger: bool = True) -> dict:
    """
    Load the series configuration file.
    Creates default config if it doesn't exist.

    Args:
        config_path: Path to config file
        use_logger: Use Prefect logger (True) or print (False) for CLI usage
    """
    if use_logger:
        logger = get_run_logger()
        log_fn = logger.info
    else:
        log_fn = print

    if not config_path.exists():
        log_fn(f"Config file not found, creating default at {config_path}")
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = get_default_config()
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

        return default_config

    with open(config_path, 'r') as f:
        config = json.load(f)

    log_fn(f"Loaded config with {len(config.get('series', []))} series")
    return config


@task(cache_policy=NO_CACHE)
def save_series_config(config: dict, config_path: Path = CONFIG_FILE) -> None:
    """Save the series configuration file."""
    logger = get_run_logger()

    config['updated_at'] = datetime.now(timezone.utc).isoformat()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    logger.info(f"Saved config to {config_path}")


@task(cache_policy=NO_CACHE)
def check_multi_downloader_nx() -> bool:
    """
    Check if multi-downloader-nx is installed and accessible.
    """
    logger = get_run_logger()

    # Check common locations
    paths_to_try = [
        "multi-downloader-nx",
        os.path.expanduser("~/bin/multi-downloader-nx"),
        os.path.expanduser("~/tools/multi-downloader-nx/multi-downloader-nx"),
    ]

    for cmd_path in paths_to_try:
        try:
            result = subprocess.run(
                [cmd_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"multi-downloader-nx v{version} found at {cmd_path}")
                return True
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            continue

    logger.error(
        "multi-downloader-nx not found. See workflows/README.md for build instructions."
    )
    return False


@task(cache_policy=NO_CACHE)
def get_downloaded_episodes(series_name: str, output_dir: Path) -> set:
    """
    Get set of already downloaded episode identifiers for a series.
    Uses the download history file maintained by multi-downloader-nx.
    """
    logger = get_run_logger()

    series_dir = output_dir / sanitize_filename(series_name)
    history_file = series_dir / "_download_history.json"

    if not history_file.exists():
        return set()

    with open(history_file, 'r') as f:
        history = json.load(f)

    downloaded = set(history.get('downloaded_episodes', []))
    logger.info(f"Found {len(downloaded)} previously downloaded episodes for {series_name}")
    return downloaded


@task(cache_policy=NO_CACHE)
def update_download_history(
    series_name: str,
    episodes: list,
    output_dir: Path,
) -> None:
    """Update the download history for a series."""
    logger = get_run_logger()

    series_dir = output_dir / sanitize_filename(series_name)
    series_dir.mkdir(parents=True, exist_ok=True)
    history_file = series_dir / "_download_history.json"

    if history_file.exists():
        with open(history_file, 'r') as f:
            history = json.load(f)
    else:
        history = {
            'series_name': series_name,
            'downloaded_episodes': [],
            'download_log': [],
        }

    # Add new episodes
    existing = set(history['downloaded_episodes'])
    for ep in episodes:
        if ep not in existing:
            history['downloaded_episodes'].append(ep)
            history['download_log'].append({
                'episode': ep,
                'downloaded_at': datetime.now(timezone.utc).isoformat(),
            })

    history['updated_at'] = datetime.now(timezone.utc).isoformat()

    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

    logger.info(f"Updated download history for {series_name}")


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip()


def find_multi_downloader_nx() -> str:
    """Find the multi-downloader-nx executable."""
    paths_to_try = [
        "multi-downloader-nx",
        os.path.expanduser("~/bin/multi-downloader-nx"),
        os.path.expanduser("~/tools/multi-downloader-nx/multi-downloader-nx"),
    ]

    for cmd_path in paths_to_try:
        try:
            result = subprocess.run(
                [cmd_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return cmd_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return "multi-downloader-nx"  # Fallback to PATH


def count_video_files(directory: Path) -> int:
    """Count video files (mkv, mp4) in a directory recursively."""
    count = 0
    if directory.exists():
        for ext in ['*.mkv', '*.mp4']:
            count += len(list(directory.rglob(ext)))
    return count


def detect_download_errors(stdout: str, stderr: str) -> Optional[str]:
    """
    Detect common error patterns in multi-downloader-nx output.
    Returns error message if found, None if no errors detected.
    """
    output = stdout + stderr

    error_patterns = [
        ("USER: Anonymous", "Not authenticated. Run: multi-downloader-nx --service crunchy --auth"),
        ("Episodes not selected!", "No episodes matched the criteria or authentication required"),
        ("404: Not Found", "Season or series not found - check the season_id"),
        ("cannot load specified objects", "Failed to load series/season data"),
        ("TOO_MANY_ACTIVE_STREAMS", "Too many active streams - try --tsd flag"),
        ("[ERROR]", "Download error occurred"),
    ]

    for pattern, message in error_patterns:
        if pattern in output:
            return message

    return None


@task(cache_policy=NO_CACHE)
def download_series(
    series_config: dict,
    global_config: dict,
    output_dir: Path,
) -> dict:
    """
    Download episodes for a single series using multi-downloader-nx.

    Args:
        series_config: Series configuration dict with season_id, episodes, etc.
        global_config: Global crunchyroll settings (quality, audio, subs)
        output_dir: Base output directory

    Returns:
        Dict with download results
    """
    logger = get_run_logger()

    series_name = series_config.get('name', 'Unknown')
    season_id = series_config.get('season_id')
    episodes = series_config.get('episodes', '1-')

    # Support legacy 'url' field by extracting series_id (but warn)
    if not season_id and series_config.get('url'):
        logger.warning(
            f"Config uses 'url' instead of 'season_id'. "
            f"Please update config to use season_id for {series_name}"
        )
        # Can't auto-convert URL to season_id - need to list seasons first
        return {
            'series_name': series_name,
            'success': False,
            'error': (
                "Config uses 'url' but season_id is required. "
                "Use list_seasons_for_series() to find the season_id, "
                "then update your config."
            ),
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }

    if not season_id:
        logger.error(f"No season_id provided for {series_name}")
        return {
            'series_name': series_name,
            'success': False,
            'error': "season_id is required in series config",
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }

    logger.info(f"Downloading {series_name} (season_id={season_id}) episodes: {episodes}")

    # Build output path
    series_dir = output_dir / sanitize_filename(series_name)
    series_dir.mkdir(parents=True, exist_ok=True)

    # Count existing video files before download
    files_before = count_video_files(series_dir)

    # Build command using -s for season_id (NOT --series which only lists)
    multi_dl_cmd = find_multi_downloader_nx()
    cmd = [
        multi_dl_cmd,
        "--service", "crunchy",
        "-s", season_id,  # Use -s for season ID (downloads)
        "-e", episodes,   # Use -e for episodes
        "-q", global_config.get('quality', '1080'),
        "--dlVideoOnce",  # Don't re-download existing
    ]

    # Add audio language if specified
    if global_config.get('audio_lang'):
        cmd.extend(["--dubLang", global_config['audio_lang']])

    # Add subtitle language if specified
    if global_config.get('subtitle_lang'):
        cmd.extend(["--dlsubs", global_config['subtitle_lang']])

    # Add MP4 output format (MKV is default)
    if global_config.get('output_format') == 'mp4':
        cmd.append("--mp4")

    logger.info(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            cwd=str(series_dir),  # Run from series directory
        )

        stdout = result.stdout or ''
        stderr = result.stderr or ''

        # Check for known error patterns
        error_msg = detect_download_errors(stdout, stderr)

        # Count files after download
        files_after = count_video_files(series_dir)
        new_files = files_after - files_before

        # Determine actual success: return code 0, no errors, and files downloaded
        # Note: If all episodes already exist (dlVideoOnce), new_files=0 is OK
        if result.returncode != 0:
            success = False
            error = error_msg or f"Command failed with return code {result.returncode}"
        elif error_msg:
            success = False
            error = error_msg
        else:
            success = True
            error = None

        download_result = {
            'series_name': series_name,
            'season_id': season_id,
            'episodes_requested': episodes,
            'success': success,
            'error': error,
            'return_code': result.returncode,
            'output_dir': str(series_dir),
            'files_before': files_before,
            'files_after': files_after,
            'new_files_downloaded': new_files,
            'stdout': stdout[-2000:],  # Last 2000 chars
            'stderr': stderr[-2000:],
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }

        if success:
            if new_files > 0:
                logger.info(f"Successfully downloaded {new_files} new files for {series_name}")
            else:
                logger.info(f"No new files for {series_name} (already downloaded or up to date)")
        else:
            logger.error(f"Failed to download {series_name}: {error}")

        return download_result

    except subprocess.TimeoutExpired:
        logger.error(f"Download timed out for {series_name}")
        return {
            'series_name': series_name,
            'season_id': season_id,
            'episodes_requested': episodes,
            'success': False,
            'error': 'Download timed out after 1 hour',
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error downloading {series_name}: {e}")
        return {
            'series_name': series_name,
            'season_id': season_id,
            'episodes_requested': episodes,
            'success': False,
            'error': str(e),
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }


@task(cache_policy=NO_CACHE)
def save_backup_manifest(
    results: list,
    output_dir: Path,
) -> Path:
    """Save a manifest of all downloads."""
    logger = get_run_logger()

    manifest = {
        'backup_timestamp': datetime.now(timezone.utc).isoformat(),
        'total_series': len(results),
        'successful': sum(1 for r in results if r.get('success')),
        'failed': sum(1 for r in results if not r.get('success')),
        'results': results,
    }

    manifest_path = output_dir / f"backup_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Saved backup manifest to {manifest_path}")
    return manifest_path


@flow(name="backup-crunchyroll-series")
def backup_crunchyroll_series(
    config_path: Path = CONFIG_FILE,
    output_dir: Path = BACKUP_DIR,
    series_filter: Optional[list] = None,
    skip_auth_check: bool = False,
) -> dict:
    """
    Main flow to backup Crunchyroll anime series.

    Args:
        config_path: Path to the series configuration JSON file
        output_dir: Base directory for downloads
        series_filter: Optional list of series names to download (None = all enabled)
        skip_auth_check: Skip authentication check (not recommended)

    Returns:
        Dict with backup results
    """
    logger = get_run_logger()
    logger.info("Starting Crunchyroll backup flow")

    # Check that multi-downloader-nx is available
    if not check_multi_downloader_nx():
        return {
            'success': False,
            'error': 'multi-downloader-nx not installed',
        }

    # Check authentication status
    if not skip_auth_check:
        auth_status = check_crunchyroll_auth()
        if not auth_status.get('authenticated'):
            logger.error("Not authenticated with Crunchyroll")
            return {
                'success': False,
                'error': 'Not authenticated with Crunchyroll',
                'auth_status': auth_status,
                'help': 'Run: multi-downloader-nx --service crunchy --auth',
            }
        logger.info(f"Authenticated as: {auth_status.get('username')}")

    # Load configuration
    config = load_series_config(config_path)
    global_config = config.get('crunchyroll_config', {})
    all_series = config.get('series', [])

    # Filter to enabled series
    enabled_series = [s for s in all_series if s.get('enabled', True)]

    # Apply name filter if provided
    if series_filter:
        enabled_series = [s for s in enabled_series if s.get('name') in series_filter]

    if not enabled_series:
        logger.warning("No series to download")
        return {
            'success': True,
            'message': 'No series configured for download',
            'series_count': 0,
        }

    logger.info(f"Downloading {len(enabled_series)} series")

    # Download each series
    results = []
    for series in enabled_series:
        result = download_series(
            series_config=series,
            global_config=global_config,
            output_dir=output_dir,
        )
        results.append(result)

    # Save manifest
    manifest_path = save_backup_manifest(results, output_dir)

    successful = sum(1 for r in results if r.get('success'))
    failed = len(results) - successful

    logger.info(f"Backup complete: {successful} successful, {failed} failed")

    return {
        'success': failed == 0,
        'total_series': len(results),
        'successful': successful,
        'failed': failed,
        'manifest_path': str(manifest_path),
        'results': results,
    }


@flow(name="download-single-crunchyroll-series")
def download_single_series(
    season_id: str,
    name: str,
    episodes: str = "1-",
    output_dir: Path = BACKUP_DIR,
    skip_auth_check: bool = False,
) -> dict:
    """
    Download a single Crunchyroll season without using config file.

    Args:
        season_id: Crunchyroll season ID (e.g., GR19CPDWM for Solo Leveling S1)
        name: Series name (for directory naming)
        episodes: Episode range (e.g., "1-12", "1-", "1,5,10")
        output_dir: Output directory
        skip_auth_check: Skip authentication check (not recommended)

    Returns:
        Dict with download result
    """
    logger = get_run_logger()
    logger.info(f"Downloading single series: {name} (season_id={season_id})")

    if not check_multi_downloader_nx():
        return {
            'success': False,
            'error': 'multi-downloader-nx not installed',
        }

    # Check authentication
    if not skip_auth_check:
        auth_status = check_crunchyroll_auth()
        if not auth_status.get('authenticated'):
            logger.error("Not authenticated with Crunchyroll")
            return {
                'success': False,
                'error': 'Not authenticated with Crunchyroll',
                'auth_status': auth_status,
                'help': 'Run: multi-downloader-nx --service crunchy --auth',
            }

    series_config = {
        'name': name,
        'season_id': season_id,
        'episodes': episodes,
    }

    global_config = {
        'quality': '1080',
        'audio_lang': 'jpn',
        'subtitle_lang': 'en',
        'output_format': 'mkv',
    }

    result = download_series(
        series_config=series_config,
        global_config=global_config,
        output_dir=output_dir,
    )

    return result


@flow(name="list-crunchyroll-seasons")
def list_seasons(series_id: str) -> dict:
    """
    List available seasons for a Crunchyroll series.
    Use this to find the season_id needed for downloads.

    Args:
        series_id: Series ID from URL (e.g., GDKHZEJ0K from .../series/GDKHZEJ0K/...)

    Returns:
        Dict with available seasons and their IDs
    """
    logger = get_run_logger()
    logger.info(f"Listing seasons for series: {series_id}")

    if not check_multi_downloader_nx():
        return {
            'success': False,
            'error': 'multi-downloader-nx not installed',
        }

    result = list_seasons_for_series(series_id)
    return result


def add_series_to_config(
    name: str,
    season_id: str,
    episodes: str = "1-",
    notes: str = "",
    config_path: Path = CONFIG_FILE,
) -> None:
    """
    Helper function to add a new series to the config file.

    Args:
        name: Series name
        season_id: Crunchyroll season ID (use --seasons to find it)
        episodes: Episode range
        notes: Optional notes about the series
        config_path: Path to config file
    """
    # Load existing config
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = get_default_config()

    # Check if series already exists
    existing_names = [s['name'] for s in config.get('series', [])]
    if name in existing_names:
        print(f"Series '{name}' already exists in config")
        return

    # Add new series
    new_series = {
        'name': name,
        'season_id': season_id,
        'episodes': episodes,
        'enabled': True,
        'notes': notes,
        'added_at': datetime.now(timezone.utc).isoformat(),
    }

    config.setdefault('series', []).append(new_series)
    config['updated_at'] = datetime.now(timezone.utc).isoformat()

    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Added '{name}' to {config_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--add":
            # Add a series interactively
            print("Add new series to config:")
            print("(Use --seasons <series_id> to find season IDs first)")
            name = input("Series name: ").strip()
            season_id = input("Season ID: ").strip()
            episodes = input("Episodes (default: 1-): ").strip() or "1-"
            notes = input("Notes (optional): ").strip()

            add_series_to_config(name, season_id, episodes, notes)

        elif sys.argv[1] == "--list":
            # List configured series
            config = load_series_config.fn(CONFIG_FILE, use_logger=False)
            print(f"\nConfigured series ({len(config.get('series', []))}):")
            for s in config.get('series', []):
                status = "enabled" if s.get('enabled', True) else "disabled"
                sid = s.get('season_id', s.get('url', 'N/A'))
                print(f"  - {s['name']} [{status}] season_id={sid} episodes={s.get('episodes', '1-')}")

        elif sys.argv[1] == "--seasons":
            # List available seasons for a series
            if len(sys.argv) < 3:
                print("Usage: python crunchyroll.py --seasons <series_id>")
                print("Example: python crunchyroll.py --seasons GDKHZEJ0K")
                print("\nTo get series_id from URL:")
                print("  https://www.crunchyroll.com/series/GDKHZEJ0K/solo-leveling")
                print("                                    ^^^^^^^^^ this is the series_id")
                sys.exit(1)

            series_id = sys.argv[2]
            result = list_seasons(series_id)

            if result.get('seasons'):
                print(f"\nSeasons for series {series_id}:")
                for s in result['seasons']:
                    ep_info = f" ({s['episode_count']} episodes)" if s.get('episode_count') else ""
                    print(f"  [S{s['season_num']}] {s['season_id']} - {s['title']}{ep_info}")
                print("\nUse the season_id with --download or --add")
            else:
                print(f"No seasons found or error occurred:")
                print(result.get('raw_output', result.get('error', 'Unknown error')))

        elif sys.argv[1] == "--download":
            # Download a single series by season ID
            if len(sys.argv) < 4:
                print("Usage: python crunchyroll.py --download <name> <season_id> [episodes]")
                print("Example: python crunchyroll.py --download 'Solo Leveling S1' GR19CPDWM 1-12")
                sys.exit(1)

            name = sys.argv[2]
            season_id = sys.argv[3]
            episodes = sys.argv[4] if len(sys.argv) > 4 else "1-"

            result = download_single_series(season_id=season_id, name=name, episodes=episodes)
            print(json.dumps(result, indent=2, default=str))

        elif sys.argv[1] == "--auth":
            # Check authentication status using a simple flow wrapper
            @flow(name="check-auth")
            def check_auth_flow():
                return check_crunchyroll_auth()

            result = check_auth_flow()
            if result.get('authenticated'):
                print(f"Authenticated as: {result.get('username')}")
            else:
                print("Not authenticated (Anonymous)")
                print("Run: multi-downloader-nx --service crunchy --auth")

        else:
            print("Usage:")
            print("  python crunchyroll.py                    # Run backup flow")
            print("  python crunchyroll.py --add              # Add series to config")
            print("  python crunchyroll.py --list             # List configured series")
            print("  python crunchyroll.py --seasons <id>     # List seasons for a series")
            print("  python crunchyroll.py --download <name> <season_id> [episodes]")
            print("  python crunchyroll.py --auth             # Check auth status")
            print("\nWorkflow:")
            print("  1. Find series_id from URL (e.g., GDKHZEJ0K from .../series/GDKHZEJ0K/...)")
            print("  2. Run --seasons <series_id> to find season_id")
            print("  3. Run --download <name> <season_id> [episodes]")
    else:
        # Run the main backup flow
        result = backup_crunchyroll_series()
        print(json.dumps(result, indent=2, default=str))
