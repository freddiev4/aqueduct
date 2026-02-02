"""
Gmail Backup Workflow using msgvault

Downloads and archives Gmail emails locally using msgvault (https://msgvault.io).
msgvault is a Go-based tool that:
- Downloads emails via Gmail API (OAuth)
- Stores in SQLite with full-text search
- Generates Parquet files for analytics via DuckDB
- Deduplicates attachments by content hash
- Supports incremental syncs via Gmail History API

Storage structure:
./backups/local/gmail/
  {email}/
    {date}/
      msgvault.db           # SQLite database
      cache/                # Parquet files
      attachments/          # Content-addressed attachments
      backup_metadata.json  # Workflow metadata

Author: Aqueduct + Claude Code
Date: 2026-02-02
"""

import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.gmail_block import GmailCredentialsBlock


# Constants
MSGVAULT_INSTALL_URL = "https://msgvault.io/install.sh"
BACKUP_DIR = Path("./backups/local/gmail")


@task(cache_policy=NO_CACHE)
def check_msgvault_installed() -> bool:
    """
    Check if msgvault binary is installed and accessible.

    Returns:
        True if msgvault is installed, False otherwise
    """
    logger = get_run_logger()

    try:
        result = subprocess.run(
            ["msgvault", "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("msgvault is installed and accessible")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    logger.warning("msgvault is not installed")
    return False


@task(cache_policy=NO_CACHE)
def install_msgvault() -> bool:
    """
    Install msgvault using the official install script.

    Returns:
        True if installation succeeded, False otherwise
    """
    logger = get_run_logger()
    logger.info("Installing msgvault...")

    try:
        # Download and run install script
        install_cmd = f"curl -fsSL {MSGVAULT_INSTALL_URL} | bash"
        result = subprocess.run(
            install_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info("msgvault installed successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"msgvault installation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("msgvault installation timed out")
        return False
    except Exception as e:
        logger.error(f"Error installing msgvault: {e}")
        return False


@task()
def ensure_msgvault() -> None:
    """
    Ensure msgvault is installed, attempt installation if not found.

    Raises:
        RuntimeError: If msgvault cannot be installed
    """
    logger = get_run_logger()

    if check_msgvault_installed():
        return

    logger.info("msgvault not found, attempting installation...")

    if not install_msgvault():
        raise RuntimeError(
            "Failed to install msgvault. Please install manually: "
            f"curl -fsSL {MSGVAULT_INSTALL_URL} | bash"
        )

    # Verify installation
    if not check_msgvault_installed():
        raise RuntimeError(
            "msgvault installation completed but binary not found in PATH"
        )


@task(cache_policy=NO_CACHE)
def initialize_database(
    db_path: Path,
    config_dir: Optional[Path] = None
) -> bool:
    """
    Initialize the msgvault SQLite database.

    Args:
        db_path: Path where the database should be created
        config_dir: Optional custom config directory

    Returns:
        True if initialization succeeded, False otherwise
    """
    logger = get_run_logger()

    # Check if database already exists
    if db_path.exists():
        logger.info(f"Database already exists at {db_path}, skipping initialization")
        return True

    # Create parent directory
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = ["msgvault", "init-db"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])

    # Set database location via environment variable (msgvault convention)
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=str(db_path.parent)
        )

        if result.returncode == 0:
            logger.info(f"Database initialized at {db_path}")
            return True
        else:
            logger.error(f"Database initialization failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Database initialization timed out")
        return False
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


@task(cache_policy=NO_CACHE)
def add_gmail_account(
    email: str,
    db_path: Path,
    config_dir: Optional[Path] = None,
    headless: bool = False
) -> bool:
    """
    Register a Gmail account with msgvault via OAuth.

    Args:
        email: Gmail address to register
        db_path: Path to the msgvault database
        config_dir: Optional custom config directory
        headless: Use device authorization flow (no browser)

    Returns:
        True if account was added successfully, False otherwise
    """
    logger = get_run_logger()

    # Build command
    cmd = ["msgvault", "add-account"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])
    if headless:
        cmd.append("--headless")

    # Set database location
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    try:
        logger.info(f"Registering Gmail account: {email}")
        if headless:
            logger.info("Using headless mode - follow the device authorization prompts")
        else:
            logger.info("Browser will open for OAuth authentication")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for OAuth flow
            env=env,
            cwd=str(db_path.parent)
        )

        if result.returncode == 0:
            logger.info(f"Account {email} registered successfully")
            return True
        else:
            # Account might already be registered
            if "already exists" in result.stderr.lower():
                logger.info(f"Account {email} already registered")
                return True
            logger.error(f"Failed to register account: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("OAuth authentication timed out")
        return False
    except Exception as e:
        logger.error(f"Error registering account: {e}")
        return False


@task(cache_policy=NO_CACHE, retries=3, retry_delay_seconds=60)
def sync_gmail_full(
    db_path: Path,
    config_dir: Optional[Path] = None,
    max_messages: Optional[int] = None,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    verbose: bool = True
) -> dict:
    """
    Perform a full sync of Gmail messages.

    Args:
        db_path: Path to the msgvault database
        config_dir: Optional custom config directory
        max_messages: Optional limit on messages to download (for testing)
        after_date: Optional start date filter (YYYY-MM-DD)
        before_date: Optional end date filter (YYYY-MM-DD)
        verbose: Enable detailed progress tracking

    Returns:
        Dict with sync statistics
    """
    logger = get_run_logger()
    logger.info("Starting full Gmail sync...")

    # Build command
    cmd = ["msgvault", "sync-full"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])
    if max_messages:
        cmd.extend(["--limit", str(max_messages)])
    if after_date:
        cmd.extend(["--after", after_date])
    if before_date:
        cmd.extend(["--before", before_date])
    if verbose:
        cmd.append("--verbose")

    # Set database location
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout (initial sync can be slow)
            env=env,
            cwd=str(db_path.parent)
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            logger.info(f"Full sync completed in {duration:.1f} seconds")
            logger.info(result.stdout)

            return {
                "success": True,
                "duration_seconds": duration,
                "output": result.stdout,
            }
        else:
            logger.error(f"Full sync failed: {result.stderr}")
            return {
                "success": False,
                "duration_seconds": duration,
                "error": result.stderr,
            }

    except subprocess.TimeoutExpired:
        logger.error("Full sync timed out after 2 hours")
        return {
            "success": False,
            "error": "Sync timed out",
            "duration_seconds": 7200,
        }
    except Exception as e:
        logger.error(f"Error during full sync: {e}")
        return {
            "success": False,
            "error": str(e),
            "duration_seconds": time.time() - start_time,
        }


@task(cache_policy=NO_CACHE, retries=3, retry_delay_seconds=30)
def sync_gmail_incremental(
    db_path: Path,
    config_dir: Optional[Path] = None
) -> dict:
    """
    Perform an incremental sync of Gmail messages using History API.

    This is much faster than full sync as it only fetches changes since
    the last sync.

    Args:
        db_path: Path to the msgvault database
        config_dir: Optional custom config directory

    Returns:
        Dict with sync statistics
    """
    logger = get_run_logger()
    logger.info("Starting incremental Gmail sync...")

    # Build command
    cmd = ["msgvault", "sync-incremental"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])

    # Set database location
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            env=env,
            cwd=str(db_path.parent)
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            logger.info(f"Incremental sync completed in {duration:.1f} seconds")
            logger.info(result.stdout)

            return {
                "success": True,
                "duration_seconds": duration,
                "output": result.stdout,
            }
        else:
            # If incremental sync fails, might need full sync
            logger.error(f"Incremental sync failed: {result.stderr}")
            return {
                "success": False,
                "duration_seconds": duration,
                "error": result.stderr,
            }

    except subprocess.TimeoutExpired:
        logger.error("Incremental sync timed out")
        return {
            "success": False,
            "error": "Sync timed out",
            "duration_seconds": 600,
        }
    except Exception as e:
        logger.error(f"Error during incremental sync: {e}")
        return {
            "success": False,
            "error": str(e),
            "duration_seconds": time.time() - start_time,
        }


@task()
def get_email_statistics(
    db_path: Path,
    config_dir: Optional[Path] = None
) -> dict:
    """
    Get email statistics from the msgvault database.

    Args:
        db_path: Path to the msgvault database
        config_dir: Optional custom config directory

    Returns:
        Dict with email statistics
    """
    logger = get_run_logger()

    # Build command
    cmd = ["msgvault", "stats"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])

    # Set database location
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=str(db_path.parent)
        )

        if result.returncode == 0:
            # Parse statistics from output
            stats = {
                "raw_output": result.stdout,
            }

            # Try to extract key metrics (msgvault stats format may vary)
            for line in result.stdout.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    stats[key.strip().lower().replace(' ', '_')] = value.strip()

            logger.info(f"Retrieved email statistics: {stats}")
            return stats
        else:
            logger.error(f"Failed to get statistics: {result.stderr}")
            return {
                "error": result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error("Statistics query timed out")
        return {"error": "Timeout"}
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {"error": str(e)}


@task()
def build_parquet_cache(
    db_path: Path,
    config_dir: Optional[Path] = None,
    full_rebuild: bool = False
) -> bool:
    """
    Build or refresh Parquet analytics cache.

    Args:
        db_path: Path to the msgvault database
        config_dir: Optional custom config directory
        full_rebuild: Clear existing cache before regenerating

    Returns:
        True if cache was built successfully, False otherwise
    """
    logger = get_run_logger()
    logger.info("Building Parquet analytics cache...")

    # Build command
    cmd = ["msgvault", "build-cache"]
    if config_dir:
        cmd.extend(["--config", str(config_dir / "config.toml")])
    if full_rebuild:
        cmd.append("--full-rebuild")

    # Set database location
    env = os.environ.copy()
    env["MSGVAULT_DB"] = str(db_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            env=env,
            cwd=str(db_path.parent)
        )

        if result.returncode == 0:
            logger.info("Parquet cache built successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"Failed to build cache: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Cache build timed out")
        return False
    except Exception as e:
        logger.error(f"Error building cache: {e}")
        return False


@task()
def save_backup_metadata(
    backup_dir: Path,
    email: str,
    sync_result: dict,
    statistics: dict,
    snapshot_date: datetime,
    workflow_duration: float
) -> Path:
    """
    Save workflow metadata to JSON file.

    Args:
        backup_dir: Backup directory for this snapshot
        email: Gmail address
        sync_result: Result from sync operation
        statistics: Email statistics
        snapshot_date: Snapshot date for this backup
        workflow_duration: Total workflow execution time

    Returns:
        Path to the saved metadata file
    """
    logger = get_run_logger()

    metadata = {
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": snapshot_date.isoformat(),
        "workflow_version": "1.0.0",
        "python_version": sys.version,
        "email": email,
        "sync_duration_seconds": sync_result.get("duration_seconds", 0),
        "sync_success": sync_result.get("success", False),
        "total_workflow_duration_seconds": workflow_duration,
        "statistics": statistics,
        "database_path": str(backup_dir / "msgvault.db"),
        "cache_path": str(backup_dir / "cache"),
    }

    # Add error info if sync failed
    if not sync_result.get("success"):
        metadata["sync_error"] = sync_result.get("error", "Unknown error")

    metadata_path = backup_dir / "backup_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    logger.info(f"Metadata saved to {metadata_path}")
    return metadata_path


@flow()
def backup_gmail(
    credentials_block_name: str,
    snapshot_date: Optional[datetime] = None,
    incremental: bool = False,
    max_messages: Optional[int] = None,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    headless: bool = False,
) -> dict:
    """
    Main flow to backup Gmail emails using msgvault.

    Args:
        credentials_block_name: Name of the GmailCredentialsBlock
        snapshot_date: Date for this backup snapshot (defaults to current UTC date)
        incremental: Use incremental sync instead of full sync
        max_messages: Optional limit on messages (for testing)
        after_date: Optional start date filter (YYYY-MM-DD)
        before_date: Optional end date filter (YYYY-MM-DD)
        headless: Use headless OAuth flow (device authorization)

    Returns:
        Dict with backup results and statistics
    """
    logger = get_run_logger()
    workflow_start = time.time()

    # Default snapshot_date to current UTC date
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif snapshot_date.tzinfo is None:
        snapshot_date = snapshot_date.replace(tzinfo=timezone.utc)

    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    logger.info(f"Starting Gmail backup workflow (snapshot: {snapshot_str})")

    # Load credentials
    credentials = GmailCredentialsBlock.load(credentials_block_name)
    email = credentials.email
    config_dir = credentials.get_config_dir()

    logger.info(f"Backing up Gmail account: {email}")

    # Setup backup directory
    backup_dir = BACKUP_DIR / email / snapshot_str
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_path = credentials.get_db_path(backup_dir)

    # Ensure msgvault is installed
    ensure_msgvault()

    # Initialize database if needed
    if not initialize_database(db_path, config_dir):
        raise RuntimeError("Failed to initialize msgvault database")

    # Register account if needed
    if not add_gmail_account(email, db_path, config_dir, headless):
        raise RuntimeError(f"Failed to register Gmail account: {email}")

    # Perform sync
    if incremental:
        logger.info("Performing incremental sync...")
        sync_result = sync_gmail_incremental(db_path, config_dir)
    else:
        logger.info("Performing full sync...")
        sync_result = sync_gmail_full(
            db_path=db_path,
            config_dir=config_dir,
            max_messages=max_messages,
            after_date=after_date,
            before_date=before_date,
        )

    if not sync_result.get("success"):
        logger.error(f"Sync failed: {sync_result.get('error')}")
        # Continue anyway to save metadata about the failure

    # Get statistics
    statistics = get_email_statistics(db_path, config_dir)

    # Build Parquet cache for analytics
    build_parquet_cache(db_path, config_dir)

    # Save metadata
    workflow_duration = time.time() - workflow_start
    metadata_path = save_backup_metadata(
        backup_dir=backup_dir,
        email=email,
        sync_result=sync_result,
        statistics=statistics,
        snapshot_date=snapshot_date,
        workflow_duration=workflow_duration,
    )

    logger.info(f"Gmail backup completed in {workflow_duration:.1f} seconds")
    logger.info(f"Backup location: {backup_dir}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Metadata: {metadata_path}")

    return {
        "email": email,
        "snapshot_date": snapshot_str,
        "backup_dir": str(backup_dir),
        "database_path": str(db_path),
        "sync_result": sync_result,
        "statistics": statistics,
        "workflow_duration_seconds": workflow_duration,
    }


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Backup Gmail using msgvault")
    parser.add_argument(
        "--credentials",
        default="gmail-credentials",
        help="Name of the GmailCredentialsBlock (default: gmail-credentials)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Use incremental sync instead of full sync"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        help="Limit number of messages to download (for testing)"
    )
    parser.add_argument(
        "--after",
        help="Only sync messages after this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--before",
        help="Only sync messages before this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use headless OAuth flow (device authorization)"
    )

    args = parser.parse_args()

    result = backup_gmail(
        credentials_block_name=args.credentials,
        incremental=args.incremental,
        max_messages=args.max_messages,
        after_date=args.after,
        before_date=args.before,
        headless=args.headless,
    )

    print(json.dumps(result, indent=2, default=str))
