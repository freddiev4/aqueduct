"""
Test script for LinkedIn workflow.

This script creates a mock LinkedIn export ZIP file for testing the workflow
without needing an actual LinkedIn data export.

Run this to verify the workflow processes data correctly.
"""

import csv
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import directly from the workflow file
workflow_path = project_root / "workflows" / "cannot-automate" / "linkedin.py"
import importlib.util
spec = importlib.util.spec_from_file_location("linkedin_workflow", workflow_path)
linkedin_workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linkedin_workflow)
process_linkedin_export = linkedin_workflow.process_linkedin_export


def create_mock_linkedin_export(output_path: Path) -> Path:
    """
    Create a mock LinkedIn data export ZIP file for testing.

    Args:
        output_path: Path where the ZIP file should be created

    Returns:
        Path to created ZIP file
    """
    print("Creating mock LinkedIn export data...")

    # Create temporary directory for mock data
    temp_dir = Path("/tmp/mock_linkedin_export")
    temp_dir.mkdir(exist_ok=True)

    # Create Profile.csv
    profile_data = [
        {
            "First Name": "John",
            "Last Name": "Doe",
            "Maiden Name": "",
            "Address": "",
            "Birth Date": "",
            "Headline": "Senior Software Engineer at Tech Corp",
            "Summary": "Experienced software engineer with 10+ years in backend development.",
            "Industry": "Computer Software",
            "ZIP Code": "",
            "Geo Location": "San Francisco Bay Area",
            "Twitter Handles": "",
            "Websites": "",
            "Instant Messengers": "",
            "Public Profile URL": "https://www.linkedin.com/in/johndoe",
        }
    ]

    with open(temp_dir / "Profile.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=profile_data[0].keys())
        writer.writeheader()
        writer.writerows(profile_data)

    # Create Connections.csv
    connections_data = [
        {
            "First Name": "Alice",
            "Last Name": "Smith",
            "Email Address": "alice.smith@example.com",
            "Company": "Design Studios Inc",
            "Position": "UX Designer",
            "Connected On": "15 Jan 2020",
        },
        {
            "First Name": "Bob",
            "Last Name": "Johnson",
            "Email Address": "bob.j@example.com",
            "Company": "Data Analytics Corp",
            "Position": "Data Scientist",
            "Connected On": "03 Mar 2021",
        },
        {
            "First Name": "Carol",
            "Last Name": "Williams",
            "Email Address": "c.williams@example.com",
            "Company": "Tech Corp",
            "Position": "Product Manager",
            "Connected On": "22 Jun 2022",
        },
    ]

    with open(temp_dir / "Connections.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=connections_data[0].keys())
        writer.writeheader()
        writer.writerows(connections_data)

    # Create Messages.csv
    messages_data = [
        {
            "CONVERSATION ID": "conv123",
            "CONVERSATION TITLE": "Alice Smith",
            "FROM": "John Doe",
            "SENDER PROFILE URL": "https://www.linkedin.com/in/johndoe",
            "TO": "Alice Smith",
            "DATE": "2024-01-15 10:30:00 UTC",
            "SUBJECT": "",
            "CONTENT": "Hey Alice! Great to connect. How's the new role going?",
            "FOLDER": "INBOX",
        },
        {
            "CONVERSATION ID": "conv123",
            "CONVERSATION TITLE": "Alice Smith",
            "FROM": "Alice Smith",
            "SENDER PROFILE URL": "https://www.linkedin.com/in/alicesmith",
            "TO": "John Doe",
            "DATE": "2024-01-15 11:15:00 UTC",
            "SUBJECT": "",
            "CONTENT": "Hi John! It's going great, thanks for asking. We should catch up sometime!",
            "FOLDER": "INBOX",
        },
    ]

    with open(temp_dir / "Messages.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=messages_data[0].keys())
        writer.writeheader()
        writer.writerows(messages_data)

    # Create Posts.csv
    posts_data = [
        {
            "Date": "2024-01-20",
            "Link": "https://www.linkedin.com/feed/update/urn:li:activity:123456789",
            "Title": "",
            "Shared Url": "",
            "Type": "ORIGINAL",
            "Text": "Excited to share that I just completed a course on distributed systems! #learning #tech",
            "Likes": "42",
            "Comments": "5",
        },
        {
            "Date": "2024-02-05",
            "Link": "https://www.linkedin.com/feed/update/urn:li:activity:987654321",
            "Title": "",
            "Shared Url": "https://techblog.com/great-article",
            "Type": "RESHARE",
            "Text": "Great insights on microservices architecture. Worth a read!",
            "Likes": "28",
            "Comments": "3",
        },
    ]

    with open(temp_dir / "Posts.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=posts_data[0].keys())
        writer.writeheader()
        writer.writerows(posts_data)

    # Create Reactions.csv
    reactions_data = [
        {
            "Date": "2024-01-18",
            "Link": "https://www.linkedin.com/feed/update/urn:li:activity:111222333",
            "Type": "LIKE",
            "Actor Name": "Bob Johnson",
        },
        {
            "Date": "2024-02-03",
            "Link": "https://www.linkedin.com/feed/update/urn:li:activity:444555666",
            "Type": "CELEBRATE",
            "Actor Name": "Carol Williams",
        },
    ]

    with open(temp_dir / "Reactions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=reactions_data[0].keys())
        writer.writeheader()
        writer.writerows(reactions_data)

    # Create Endorsements Given.csv
    endorsements_given = [
        {
            "Endorser First Name": "John",
            "Endorser Last Name": "Doe",
            "Endorsee First Name": "Alice",
            "Endorsee Last Name": "Smith",
            "Skill": "User Experience Design",
            "Endorsement Date": "2023-05-15",
        },
    ]

    with open(
        temp_dir / "Endorsements Given.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=endorsements_given[0].keys())
        writer.writeheader()
        writer.writerows(endorsements_given)

    # Create Endorsements Received.csv
    endorsements_received = [
        {
            "Endorser First Name": "Alice",
            "Endorser Last Name": "Smith",
            "Endorsee First Name": "John",
            "Endorsee Last Name": "Doe",
            "Skill": "Python",
            "Endorsement Date": "2023-06-20",
        },
        {
            "Endorser First Name": "Bob",
            "Endorser Last Name": "Johnson",
            "Endorsee First Name": "John",
            "Endorsee Last Name": "Doe",
            "Skill": "System Design",
            "Endorsement Date": "2023-08-10",
        },
    ]

    with open(
        temp_dir / "Endorsements Received.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=endorsements_received[0].keys())
        writer.writeheader()
        writer.writerows(endorsements_received)

    # Create ZIP file
    print(f"Creating ZIP file at {output_path}...")
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in temp_dir.glob("*.csv"):
            zf.write(file_path, arcname=file_path.name)

    # Clean up temp directory
    shutil.rmtree(temp_dir)

    print(f"Mock LinkedIn export created: {output_path}")
    return output_path


def test_linkedin_workflow():
    """
    Test the LinkedIn workflow with mock data.
    """
    print("=" * 70)
    print("LinkedIn Workflow Test")
    print("=" * 70)
    print()

    # Create mock export ZIP
    test_zip = Path("/tmp/test_linkedin_export.zip")
    create_mock_linkedin_export(test_zip)

    print()
    print("-" * 70)
    print("Running workflow...")
    print("-" * 70)
    print()

    # Run workflow
    result = process_linkedin_export(
        zip_path=test_zip,
        export_date="2026-02-10",
        username=None,  # Auto-detect
        keep_extracted=False,
    )

    print()
    print("=" * 70)
    print("Test Results")
    print("=" * 70)
    print()
    print(f"Success: {result['success']}")
    print(f"Username: {result['username']}")
    print(f"Export Date: {result['export_date']}")
    print(f"Processing Time: {result['processing_time_seconds']}s")
    print()
    print("Data Summary:")
    for key, value in result["data_summary"].items():
        print(f"  {key}: {value}")
    print()
    print(f"Export Directory: {result['export_dir']}")
    print(f"Processed Directory: {result['processed_dir']}")
    print(f"Metadata File: {result['metadata_path']}")
    print(f"Archive Directory: {result['archive_dir']}")
    print()

    # Verify files were created
    export_dir = Path(result["export_dir"])
    processed_dir = Path(result["processed_dir"])

    print("Verifying created files...")
    expected_files = [
        "profile.json",
        "connections.json",
        "messages.json",
        "posts.json",
        "reactions.json",
        "endorsements.json",
        "csv_index.json",
    ]

    for filename in expected_files:
        file_path = processed_dir / filename
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"  ✓ {filename} ({size_kb:.2f} KB)")
        else:
            print(f"  ✗ {filename} (missing!)")

    # Display sample data
    print()
    print("-" * 70)
    print("Sample Data from connections.json:")
    print("-" * 70)
    connections_file = processed_dir / "connections.json"
    if connections_file.exists():
        with open(connections_file, "r") as f:
            connections = json.load(f)
        print(f"Connection Count: {connections['connection_count']}")
        print(f"First Connection: {connections['connections'][0]['First Name']} {connections['connections'][0]['Last Name']}")
        print(f"Company: {connections['connections'][0]['Company']}")

    print()
    print("=" * 70)
    print("Test Complete!")
    print("=" * 70)
    print()
    print(f"You can inspect the backup at: {export_dir}")
    print()

    # Clean up test ZIP
    test_zip.unlink()


if __name__ == "__main__":
    test_linkedin_workflow()
