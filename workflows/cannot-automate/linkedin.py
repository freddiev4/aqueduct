"""
LinkedIn Backup Workflow

Processes downloaded LinkedIn data export ZIP files and organizes them into
searchable backups. Since LinkedIn does not provide an automatable API for
personal data export, this workflow handles the manual export process.

LinkedIn Data Export Process:
1. Go to Settings & Privacy > Data Privacy > "Get a copy of your data"
2. Select "Fast" (selected data) or "Complete" (full archive)
3. Select the data types you want (Recommended: select all)
4. Click "Request archive"
5. Wait for email notification (typically within 24 hours)
6. Download the ZIP file from the link in the email (expires in 72 hours)
7. Run this workflow with the path to the downloaded ZIP file

Supported Data Types:
- Profile information (Profile.csv)
- Connections (Connections.csv, Invitations.csv)
- Messages (Messages.csv, messages/ folder)
- Posts and shares (Shares.csv, Posts.csv)
- Reactions and comments (Reactions.csv, Comments.csv)
- Articles (Articles/)
- Endorsements (Endorsements Received.csv, Endorsements Given.csv)
- Recommendations (Recommendations Received.csv, Recommendations Given.csv)
- Contacts (Contacts.csv, contacts.vcf)
- Learning courses (Learning.csv)
- Job applications (Job Applicant Saved Answers.csv)
- And more depending on LinkedIn's export format

All timestamps are stored in UTC timezone for consistency.

Why this workflow is in cannot-automate/:
- LinkedIn removed public API access in 2015
- Current APIs require LinkedIn Partner approval (not available to individuals)
- No API exists to automate the data export request or download
- Unofficial scraping methods violate LinkedIn's Terms of Service
- High risk of account suspension with automation attempts
"""

import csv
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BACKUP_DIR = Path("./backups/local/linkedin")


@task(cache_policy=NO_CACHE)
def validate_zip_file(zip_path: Path) -> dict:
    """
    Validate that the provided file is a valid LinkedIn export ZIP.

    Args:
        zip_path: Path to the LinkedIn export ZIP file

    Returns:
        Dictionary with validation results and metadata

    Raises:
        ValueError: If file is not a valid ZIP or doesn't look like a LinkedIn export
    """
    logger = get_run_logger()

    if not zip_path.exists():
        raise ValueError(f"ZIP file not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"File is not a valid ZIP archive: {zip_path}")

    logger.info(f"Validating LinkedIn export ZIP: {zip_path}")

    # Open and inspect the ZIP contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        file_list = zf.namelist()

        # Look for typical LinkedIn export files
        expected_patterns = [
            "Profile.csv",
            "Connections.csv",
            "Messages.csv",
            "Shares.csv",
        ]

        found_patterns = []
        for pattern in expected_patterns:
            matching_files = [f for f in file_list if pattern in f]
            if matching_files:
                found_patterns.append(pattern)

        if not found_patterns:
            logger.warning(
                "ZIP file doesn't contain typical LinkedIn export files. "
                "This may not be a LinkedIn data export. Proceeding anyway..."
            )

        # Get ZIP metadata
        metadata = {
            "zip_path": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_size_mb": round(zip_path.stat().st_size / (1024 * 1024), 2),
            "total_files": len(file_list),
            "found_patterns": found_patterns,
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"ZIP contains {len(file_list)} files ({metadata['zip_size_mb']} MB)")
        logger.info(f"Found LinkedIn export files: {', '.join(found_patterns)}")

        return metadata


@task(cache_policy=NO_CACHE)
def extract_zip_file(zip_path: Path, extract_dir: Path) -> Path:
    """
    Extract the LinkedIn ZIP file to a temporary directory.

    Args:
        zip_path: Path to the LinkedIn export ZIP file
        extract_dir: Directory to extract files to

    Returns:
        Path to the extraction directory
    """
    logger = get_run_logger()

    # Create extraction directory
    extract_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extracting ZIP to {extract_dir}...")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        logger.info(f"Successfully extracted {len(list(extract_dir.rglob('*')))} items")
        return extract_dir

    except Exception as e:
        logger.error(f"Failed to extract ZIP file: {e}")
        raise


@task(cache_policy=NO_CACHE)
def detect_username_from_export(extract_dir: Path) -> str:
    """
    Attempt to detect the LinkedIn username from the export data.
    Falls back to 'unknown' if not found.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        LinkedIn username or 'unknown'
    """
    logger = get_run_logger()

    # Try to find username from Profile.csv
    profile_files = list(extract_dir.rglob("Profile.csv"))
    if profile_files:
        try:
            with open(profile_files[0], "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # LinkedIn Profile.csv may have different column names
                    possible_username_fields = [
                        "Public Profile URL",
                        "Profile URL",
                        "LinkedIn URL",
                        "vanity_name",
                    ]
                    for field in possible_username_fields:
                        if field in row and row[field]:
                            # Extract username from URL like linkedin.com/in/username
                            url = row[field]
                            if "/in/" in url:
                                username = url.split("/in/")[-1].strip("/")
                                logger.info(f"Detected username from profile: {username}")
                                return username
        except Exception as e:
            logger.warning(f"Failed to parse Profile.csv: {e}")

    # Fallback: use directory name if it looks like a LinkedIn export
    extract_dir_name = extract_dir.name
    if "linkedin" in extract_dir_name.lower():
        logger.info(f"Using directory name as username: {extract_dir_name}")
        return extract_dir_name

    logger.warning("Could not detect username from export, using 'unknown'")
    return "unknown"


@task(cache_policy=NO_CACHE)
def parse_csv_file(csv_path: Path) -> list[dict]:
    """
    Parse a CSV file from LinkedIn export into a list of dictionaries.

    Args:
        csv_path: Path to CSV file

    Returns:
        List of dictionaries, one per CSV row
    """
    logger = get_run_logger()

    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info(f"Parsed {len(rows)} rows from {csv_path.name}")
        return rows

    except Exception as e:
        logger.error(f"Failed to parse CSV {csv_path}: {e}")
        return []


@task(cache_policy=NO_CACHE)
def process_profile_data(extract_dir: Path) -> Optional[dict]:
    """
    Process Profile.csv to extract profile information.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with profile data or None if not found
    """
    logger = get_run_logger()

    profile_files = list(extract_dir.rglob("Profile.csv"))
    if not profile_files:
        logger.warning("Profile.csv not found in export")
        return None

    profile_path = profile_files[0]
    rows = parse_csv_file(profile_path)

    if not rows:
        return None

    # LinkedIn Profile.csv typically has one row with multiple columns
    profile_data = {
        "source_file": profile_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "data": rows[0] if rows else {},
    }

    logger.info(f"Processed profile data with {len(rows[0])} fields")
    return profile_data


@task(cache_policy=NO_CACHE)
def process_connections_data(extract_dir: Path) -> Optional[dict]:
    """
    Process Connections.csv to extract connection information.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with connections data or None if not found
    """
    logger = get_run_logger()

    connections_files = list(extract_dir.rglob("Connections.csv"))
    if not connections_files:
        logger.warning("Connections.csv not found in export")
        return None

    connections_path = connections_files[0]
    rows = parse_csv_file(connections_path)

    if not rows:
        return None

    # Sort connections by connected date if available
    if rows and "Connected On" in rows[0]:
        try:
            rows.sort(key=lambda x: x.get("Connected On", ""))
        except Exception as e:
            logger.warning(f"Failed to sort connections: {e}")

    connections_data = {
        "source_file": connections_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "connection_count": len(rows),
        "connections": rows,
    }

    logger.info(f"Processed {len(rows)} connections")
    return connections_data


@task(cache_policy=NO_CACHE)
def process_messages_data(extract_dir: Path) -> Optional[dict]:
    """
    Process Messages.csv to extract message history.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with messages data or None if not found
    """
    logger = get_run_logger()

    messages_files = list(extract_dir.rglob("Messages.csv"))
    if not messages_files:
        logger.warning("Messages.csv not found in export")
        return None

    messages_path = messages_files[0]
    rows = parse_csv_file(messages_path)

    if not rows:
        return None

    # Sort messages by date if available
    if rows and "DATE" in rows[0]:
        try:
            rows.sort(key=lambda x: x.get("DATE", ""))
        except Exception as e:
            logger.warning(f"Failed to sort messages: {e}")

    messages_data = {
        "source_file": messages_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(rows),
        "messages": rows,
    }

    logger.info(f"Processed {len(rows)} messages")
    return messages_data


@task(cache_policy=NO_CACHE)
def process_posts_data(extract_dir: Path) -> Optional[dict]:
    """
    Process Posts.csv and Shares.csv to extract post history.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with posts data or None if not found
    """
    logger = get_run_logger()

    # LinkedIn may use different file names for posts
    post_file_patterns = ["Posts.csv", "Shares.csv", "Share.csv"]
    posts_files = []

    for pattern in post_file_patterns:
        found = list(extract_dir.rglob(pattern))
        if found:
            posts_files.extend(found)

    if not posts_files:
        logger.warning("No posts/shares CSV files found in export")
        return None

    all_posts = []
    for posts_path in posts_files:
        rows = parse_csv_file(posts_path)
        if rows:
            # Add source file to each row
            for row in rows:
                row["_source_file"] = posts_path.name
            all_posts.extend(rows)

    if not all_posts:
        return None

    # Sort posts by date if available
    date_fields = ["Date", "DATE", "SharedAt", "Shared At", "Created Date"]
    for date_field in date_fields:
        if all_posts and date_field in all_posts[0]:
            try:
                all_posts.sort(key=lambda x: x.get(date_field, ""))
                break
            except Exception as e:
                logger.warning(f"Failed to sort posts by {date_field}: {e}")

    posts_data = {
        "source_files": [f.name for f in posts_files],
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "post_count": len(all_posts),
        "posts": all_posts,
    }

    logger.info(f"Processed {len(all_posts)} posts from {len(posts_files)} file(s)")
    return posts_data


@task(cache_policy=NO_CACHE)
def process_reactions_data(extract_dir: Path) -> Optional[dict]:
    """
    Process Reactions.csv to extract reaction history.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with reactions data or None if not found
    """
    logger = get_run_logger()

    reactions_files = list(extract_dir.rglob("Reactions.csv"))
    if not reactions_files:
        logger.info("Reactions.csv not found in export (optional)")
        return None

    reactions_path = reactions_files[0]
    rows = parse_csv_file(reactions_path)

    if not rows:
        return None

    reactions_data = {
        "source_file": reactions_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "reaction_count": len(rows),
        "reactions": rows,
    }

    logger.info(f"Processed {len(rows)} reactions")
    return reactions_data


@task(cache_policy=NO_CACHE)
def process_endorsements_data(extract_dir: Path) -> Optional[dict]:
    """
    Process endorsement-related CSV files.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary with endorsements data or None if not found
    """
    logger = get_run_logger()

    endorsements_files = list(extract_dir.rglob("Endorsement*.csv"))
    if not endorsements_files:
        logger.info("Endorsement CSV files not found in export (optional)")
        return None

    all_endorsements = {}

    for endorse_path in endorsements_files:
        rows = parse_csv_file(endorse_path)
        if rows:
            # Use filename (without .csv) as key
            key = endorse_path.stem
            all_endorsements[key] = {
                "source_file": endorse_path.name,
                "count": len(rows),
                "data": rows,
            }

    if not all_endorsements:
        return None

    endorsements_data = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "categories": all_endorsements,
    }

    total = sum(cat["count"] for cat in all_endorsements.values())
    logger.info(f"Processed {total} endorsements from {len(endorsements_files)} file(s)")
    return endorsements_data


@task(cache_policy=NO_CACHE)
def process_all_csv_files(extract_dir: Path) -> dict:
    """
    Find and process all CSV files in the export directory.
    Creates a comprehensive index of all available data.

    Args:
        extract_dir: Directory containing extracted LinkedIn data

    Returns:
        Dictionary mapping CSV filenames to their parsed data
    """
    logger = get_run_logger()

    all_csv_files = list(extract_dir.rglob("*.csv"))
    logger.info(f"Found {len(all_csv_files)} CSV files in export")

    csv_index = {}

    for csv_path in all_csv_files:
        # Use relative path from extract_dir as key
        relative_path = csv_path.relative_to(extract_dir)
        key = str(relative_path).replace(".csv", "").replace("/", "_").replace("\\", "_")

        rows = parse_csv_file(csv_path)

        csv_index[key] = {
            "file_path": str(relative_path),
            "file_name": csv_path.name,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
            "sample_row": rows[0] if rows else None,
        }

    logger.info(f"Indexed {len(csv_index)} CSV files")
    return csv_index


@task(cache_policy=NO_CACHE)
def save_processed_data(
    username: str,
    export_date: str,
    profile_data: Optional[dict],
    connections_data: Optional[dict],
    messages_data: Optional[dict],
    posts_data: Optional[dict],
    reactions_data: Optional[dict],
    endorsements_data: Optional[dict],
    csv_index: dict,
    zip_metadata: dict,
    output_dir: Path = BACKUP_DIR,
) -> dict:
    """
    Save all processed LinkedIn data to organized directory structure.

    Args:
        username: LinkedIn username
        export_date: Date string for this export (YYYY-MM-DD)
        profile_data: Processed profile data
        connections_data: Processed connections data
        messages_data: Processed messages data
        posts_data: Processed posts data
        reactions_data: Processed reactions data
        endorsements_data: Processed endorsements data
        csv_index: Index of all CSV files
        zip_metadata: Metadata about the ZIP file
        output_dir: Base backup directory

    Returns:
        Dictionary with save statistics
    """
    logger = get_run_logger()

    # Create directory structure: linkedin/{username}/exports/{export_date}/
    export_dir = output_dir / username / "exports" / export_date
    export_dir.mkdir(parents=True, exist_ok=True)

    processed_dir = export_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []

    # Save each data type
    data_types = {
        "profile.json": profile_data,
        "connections.json": connections_data,
        "messages.json": messages_data,
        "posts.json": posts_data,
        "reactions.json": reactions_data,
        "endorsements.json": endorsements_data,
        "csv_index.json": csv_index,
    }

    for filename, data in data_types.items():
        if data:
            file_path = processed_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            saved_files.append(str(file_path))
            logger.info(f"Saved {filename}")

    # Save comprehensive metadata
    metadata = {
        "export_date": export_date,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "workflow_version": "1.0.0",
        "python_version": sys.version,
        "zip_metadata": zip_metadata,
        "data_summary": {
            "profile": bool(profile_data),
            "connections_count": connections_data.get("connection_count", 0) if connections_data else 0,
            "messages_count": messages_data.get("message_count", 0) if messages_data else 0,
            "posts_count": posts_data.get("post_count", 0) if posts_data else 0,
            "reactions_count": reactions_data.get("reaction_count", 0) if reactions_data else 0,
            "csv_files_indexed": len(csv_index),
        },
        "saved_files": saved_files,
    }

    metadata_path = export_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Saved metadata to {metadata_path}")

    return {
        "export_dir": str(export_dir),
        "processed_dir": str(processed_dir),
        "metadata_path": str(metadata_path),
        "files_saved": len(saved_files),
        "data_summary": metadata["data_summary"],
    }


@task(cache_policy=NO_CACHE)
def copy_original_export(
    extract_dir: Path,
    username: str,
    export_date: str,
    output_dir: Path = BACKUP_DIR,
) -> Path:
    """
    Copy the original extracted files to the backup directory for archival.

    Args:
        extract_dir: Directory containing extracted LinkedIn data
        username: LinkedIn username
        export_date: Date string for this export
        output_dir: Base backup directory

    Returns:
        Path to the archived original export
    """
    logger = get_run_logger()

    archive_dir = output_dir / username / "exports" / export_date / "original"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Copy all files from extract_dir to archive_dir
    for item in extract_dir.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(extract_dir)
            dest_path = archive_dir / relative_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_path)

    logger.info(f"Archived original export to {archive_dir}")
    return archive_dir


@flow(name="process-linkedin-export")
def process_linkedin_export(
    zip_path: Path,
    export_date: Optional[str] = None,
    username: Optional[str] = None,
    output_dir: Path = BACKUP_DIR,
    keep_extracted: bool = False,
) -> dict:
    """
    Main flow to process a downloaded LinkedIn data export ZIP file.

    Args:
        zip_path: Path to the downloaded LinkedIn export ZIP file
        export_date: Date string for this export (YYYY-MM-DD). If None, uses today's date.
        username: LinkedIn username. If None, attempts to detect from export.
        output_dir: Base directory for backups
        keep_extracted: Whether to keep the extracted temporary directory

    Returns:
        Dictionary with processing results
    """
    logger = get_run_logger()
    workflow_start = time.time()

    # Set export date to today if not provided
    if export_date is None:
        export_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Starting LinkedIn export processing (export date: {export_date})")
    logger.info(f"ZIP file: {zip_path}")

    # Convert to Path object if string
    zip_path = Path(zip_path)

    # Validate ZIP file
    zip_metadata = validate_zip_file(zip_path)

    # Create temporary extraction directory
    temp_dir = Path("/tmp") / f"linkedin_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    extract_dir = extract_zip_file(zip_path, temp_dir)

    # Detect username if not provided
    if username is None:
        username = detect_username_from_export(extract_dir)

    logger.info(f"Processing export for user: {username}")

    # Process all data types
    profile_data = process_profile_data(extract_dir)
    connections_data = process_connections_data(extract_dir)
    messages_data = process_messages_data(extract_dir)
    posts_data = process_posts_data(extract_dir)
    reactions_data = process_reactions_data(extract_dir)
    endorsements_data = process_endorsements_data(extract_dir)

    # Create comprehensive CSV index
    csv_index = process_all_csv_files(extract_dir)

    # Save all processed data
    save_result = save_processed_data(
        username=username,
        export_date=export_date,
        profile_data=profile_data,
        connections_data=connections_data,
        messages_data=messages_data,
        posts_data=posts_data,
        reactions_data=reactions_data,
        endorsements_data=endorsements_data,
        csv_index=csv_index,
        zip_metadata=zip_metadata,
        output_dir=output_dir,
    )

    # Copy original export for archival
    archive_dir = copy_original_export(extract_dir, username, export_date, output_dir)

    # Clean up temporary directory
    if not keep_extracted:
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary directory: {e}")

    processing_time = time.time() - workflow_start

    result = {
        "success": True,
        "username": username,
        "export_date": export_date,
        "zip_path": str(zip_path),
        "export_dir": save_result["export_dir"],
        "processed_dir": save_result["processed_dir"],
        "metadata_path": save_result["metadata_path"],
        "archive_dir": str(archive_dir),
        "files_saved": save_result["files_saved"],
        "data_summary": save_result["data_summary"],
        "processing_time_seconds": round(processing_time, 2),
    }

    logger.info(f"Successfully processed LinkedIn export in {processing_time:.2f} seconds")
    logger.info(f"Data saved to: {save_result['export_dir']}")

    return result


if __name__ == "__main__":
    # Example usage
    # Replace with the path to your downloaded LinkedIn export ZIP file
    zip_file = Path("./linkedin_export.zip")

    if not zip_file.exists():
        print(f"ERROR: ZIP file not found: {zip_file}")
        print("\nTo download your LinkedIn data:")
        print("1. Go to Settings & Privacy > Data Privacy > 'Get a copy of your data'")
        print("2. Select data types and click 'Request archive'")
        print("3. Wait for email notification (usually within 24 hours)")
        print("4. Download the ZIP file and update the path in this script")
        sys.exit(1)

    result = process_linkedin_export(
        zip_path=zip_file,
        export_date=None,  # Uses today's date
        username=None,  # Auto-detected from export
        keep_extracted=False,  # Clean up temporary files
    )

    print("\n" + "=" * 60)
    print("LinkedIn Export Processing Complete!")
    print("=" * 60)
    print(f"Username: {result['username']}")
    print(f"Export Date: {result['export_date']}")
    print(f"Processing Time: {result['processing_time_seconds']}s")
    print(f"\nData Summary:")
    for key, value in result["data_summary"].items():
        print(f"  {key}: {value}")
    print(f"\nData saved to: {result['export_dir']}")
    print("=" * 60)
