"""
Crunchyroll Anime Backup Workflow

Downloads anime episodes from Crunchyroll using multi-downloader-nx.
Requires:
- multi-downloader-nx installed (npm install -g multi-downloader-nx)
- ffmpeg installed
- MKVtoolNix installed
- Crunchyroll Premium subscription

Series configuration is stored in a JSON file that can be edited to add
new series or update episode ranges.
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
        "version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "crunchyroll_config": {
            "quality": "1080",
            "audio_lang": "jaJP",
            "subtitle_lang": "enUS",
            "output_format": "mkv",
        },
        "series": [
            # Example entry:
            # {
            #     "name": "Solo Leveling",
            #     "url": "https://www.crunchyroll.com/series/GDKHZEJ0K/solo-leveling",
            #     "episodes": "1-",  # All episodes
            #     "enabled": True,
            #     "notes": "Season 1"
            # }
        ]
    }


@task(cache_policy=NO_CACHE)
def load_series_config(config_path: Path = CONFIG_FILE) -> dict:
    """
    Load the series configuration file.
    Creates default config if it doesn't exist.
    """
    logger = get_run_logger()

    if not config_path.exists():
        logger.info(f"Config file not found, creating default at {config_path}")
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = get_default_config()
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

        return default_config

    with open(config_path, 'r') as f:
        config = json.load(f)

    logger.info(f"Loaded config with {len(config.get('series', []))} series")
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

    try:
        result = subprocess.run(
            ["multi-downloader-nx", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("multi-downloader-nx is available")
            return True
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass

    # Try npx as fallback
    try:
        result = subprocess.run(
            ["npx", "multi-downloader-nx", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("multi-downloader-nx is available via npx")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    logger.error(
        "multi-downloader-nx not found. Install with: npm install -g multi-downloader-nx"
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


@task(cache_policy=NO_CACHE)
def download_series(
    series_config: dict,
    global_config: dict,
    output_dir: Path,
) -> dict:
    """
    Download episodes for a single series using multi-downloader-nx.

    Args:
        series_config: Series configuration dict with url, episodes, etc.
        global_config: Global crunchyroll settings (quality, audio, subs)
        output_dir: Base output directory

    Returns:
        Dict with download results
    """
    logger = get_run_logger()

    series_name = series_config.get('name', 'Unknown')
    series_url = series_config['url']
    episodes = series_config.get('episodes', '1-')

    logger.info(f"Downloading {series_name} episodes: {episodes}")

    # Build output path
    series_dir = output_dir / sanitize_filename(series_name)
    series_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        "multi-downloader-nx",
        "--service", "crunchy",
        "--series", series_url,
        "--episodes", episodes,
        "--q", global_config.get('quality', '1080'),
        "--dlVideoOnce",  # Don't re-download existing
        "-o", str(series_dir),
    ]

    # Add audio language if specified
    if global_config.get('audio_lang'):
        cmd.extend(["--audio", global_config['audio_lang']])

    # Add subtitle language if specified
    if global_config.get('subtitle_lang'):
        cmd.extend(["--sub", global_config['subtitle_lang']])

    # Add MKV output format
    if global_config.get('output_format') == 'mkv':
        cmd.append("--mkv")

    logger.info(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            cwd=str(output_dir),
        )

        success = result.returncode == 0

        download_result = {
            'series_name': series_name,
            'series_url': series_url,
            'episodes_requested': episodes,
            'success': success,
            'return_code': result.returncode,
            'output_dir': str(series_dir),
            'stdout': result.stdout[-2000:] if result.stdout else '',  # Last 2000 chars
            'stderr': result.stderr[-2000:] if result.stderr else '',
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }

        if success:
            logger.info(f"Successfully downloaded {series_name}")
        else:
            logger.error(f"Failed to download {series_name}: {result.stderr[:500]}")

        return download_result

    except subprocess.TimeoutExpired:
        logger.error(f"Download timed out for {series_name}")
        return {
            'series_name': series_name,
            'series_url': series_url,
            'episodes_requested': episodes,
            'success': False,
            'error': 'Download timed out after 1 hour',
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error downloading {series_name}: {e}")
        return {
            'series_name': series_name,
            'series_url': series_url,
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
) -> dict:
    """
    Main flow to backup Crunchyroll anime series.

    Args:
        config_path: Path to the series configuration JSON file
        output_dir: Base directory for downloads
        series_filter: Optional list of series names to download (None = all enabled)

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
    url: str,
    name: str,
    episodes: str = "1-",
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Download a single Crunchyroll series without using config file.

    Args:
        url: Crunchyroll series URL
        name: Series name (for directory naming)
        episodes: Episode range (e.g., "1-12", "1-", "1,5,10")
        output_dir: Output directory

    Returns:
        Dict with download result
    """
    logger = get_run_logger()
    logger.info(f"Downloading single series: {name}")

    if not check_multi_downloader_nx():
        return {
            'success': False,
            'error': 'multi-downloader-nx not installed',
        }

    series_config = {
        'name': name,
        'url': url,
        'episodes': episodes,
    }

    global_config = {
        'quality': '1080',
        'audio_lang': 'jaJP',
        'subtitle_lang': 'enUS',
        'output_format': 'mkv',
    }

    result = download_series(
        series_config=series_config,
        global_config=global_config,
        output_dir=output_dir,
    )

    return result


def add_series_to_config(
    name: str,
    url: str,
    episodes: str = "1-",
    notes: str = "",
    config_path: Path = CONFIG_FILE,
) -> None:
    """
    Helper function to add a new series to the config file.

    Args:
        name: Series name
        url: Crunchyroll series URL
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
        'url': url,
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
            name = input("Series name: ").strip()
            url = input("Crunchyroll URL: ").strip()
            episodes = input("Episodes (default: 1-): ").strip() or "1-"
            notes = input("Notes (optional): ").strip()

            add_series_to_config(name, url, episodes, notes)

        elif sys.argv[1] == "--list":
            # List configured series
            config = load_series_config.fn(CONFIG_FILE)
            print(f"\nConfigured series ({len(config.get('series', []))}):")
            for s in config.get('series', []):
                status = "enabled" if s.get('enabled', True) else "disabled"
                print(f"  - {s['name']} [{status}] episodes: {s.get('episodes', '1-')}")

        elif sys.argv[1] == "--download":
            # Download a single series by URL
            if len(sys.argv) < 4:
                print("Usage: python crunchyroll.py --download <name> <url> [episodes]")
                sys.exit(1)

            name = sys.argv[2]
            url = sys.argv[3]
            episodes = sys.argv[4] if len(sys.argv) > 4 else "1-"

            result = download_single_series(url=url, name=name, episodes=episodes)
            print(json.dumps(result, indent=2, default=str))

        else:
            print("Usage:")
            print("  python crunchyroll.py           # Run backup flow")
            print("  python crunchyroll.py --add     # Add series to config")
            print("  python crunchyroll.py --list    # List configured series")
            print("  python crunchyroll.py --download <name> <url> [episodes]")
    else:
        # Run the main backup flow
        result = backup_crunchyroll_series()
        print(json.dumps(result, indent=2, default=str))
