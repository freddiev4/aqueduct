# LinkedIn Workflow Documentation

**Status:** Cannot Automate
**Location:** `workflows/cannot-automate/linkedin.py`
**Created:** 2026-02-10

## Overview

The LinkedIn workflow processes manually downloaded LinkedIn data export ZIP files and organizes them into searchable, structured backups. This workflow is in the `cannot-automate/` directory because LinkedIn does not provide API access for automated personal data export.

## Why Manual?

### API Restrictions

1. **No Public API**: LinkedIn shut down public API access in 2015
2. **Partnership Required**: Current APIs only available to approved LinkedIn Partners
3. **Restricted Scopes**: Even partners have limited access to personal data
4. **No Export API**: No API endpoint to automate data export requests or downloads

### Alternatives Considered

| Method | Status | Issue |
|--------|--------|-------|
| Official LinkedIn APIs | Not Available | Requires partnership approval |
| linkedin-api (PyPI) | Violates ToS | Uses internal Voyager API, account ban risk |
| Selenium Automation | Unreliable | Anti-bot detection, email verification, ToS violation |
| Manual Export | ✓ Viable | ToS compliant, reliable, what we implement |

## How It Works

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Manual LinkedIn Export                        │
│  (Settings > Data Privacy > Get a copy of your data)           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                         (24 hour wait)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Download ZIP from Email Link                       │
│                   (expires in 72 hours)                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│           Run process_linkedin_export() workflow                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────┐       ┌──────────────┐
│  Validate    │      │   Extract    │       │    Detect    │
│  ZIP File    │──────│   ZIP to     │───────│   Username   │
│              │      │   Temp Dir   │       │              │
└──────────────┘      └──────────────┘       └──────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────┐       ┌──────────────┐
│Parse Profile │      │Parse Connect │       │Parse Messages│
│   Data       │      │   ions Data  │       │   Data       │
└──────────────┘      └──────────────┘       └──────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────┐       ┌──────────────┐
│ Parse Posts  │      │Parse Reactions│      │Parse Endorse-│
│   Data       │      │   Data       │       │  ments       │
└──────────────┘      └──────────────┘       └──────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌─────────────────────┐
                    │  Index All CSV      │
                    │  Files              │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Save Processed      │
                    │ Data as JSON        │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Archive Original    │
                    │ CSV Files           │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Generate Metadata   │
                    │ & Summary           │
                    └─────────────────────┘
```

### Task Breakdown

#### 1. `validate_zip_file(zip_path)`
- Validates the file is a proper ZIP archive
- Checks for typical LinkedIn export files (Profile.csv, Connections.csv, etc.)
- Returns metadata about ZIP size and contents

#### 2. `extract_zip_file(zip_path, extract_dir)`
- Extracts ZIP to temporary directory
- Returns path to extraction directory

#### 3. `detect_username_from_export(extract_dir)`
- Attempts to parse username from Profile.csv
- Falls back to directory name or "unknown"

#### 4. `parse_csv_file(csv_path)`
- Generic CSV parser
- Returns list of dictionaries (one per row)
- Handles encoding issues

#### 5. `process_profile_data(extract_dir)`
- Finds and parses Profile.csv
- Extracts profile information
- Returns structured dictionary

#### 6. `process_connections_data(extract_dir)`
- Finds and parses Connections.csv
- Sorts by connection date
- Returns connections list

#### 7. `process_messages_data(extract_dir)`
- Finds and parses Messages.csv
- Sorts by date
- Returns message history

#### 8. `process_posts_data(extract_dir)`
- Finds Posts.csv and/or Shares.csv
- Combines multiple sources if found
- Sorts by date
- Returns posts list

#### 9. `process_reactions_data(extract_dir)`
- Finds and parses Reactions.csv (optional)
- Returns reactions list

#### 10. `process_endorsements_data(extract_dir)`
- Finds all Endorsement*.csv files
- Processes received and given endorsements
- Returns categorized endorsements

#### 11. `process_all_csv_files(extract_dir)`
- Scans for ALL CSV files recursively
- Creates comprehensive index with:
  - File paths
  - Row counts
  - Column names
  - Sample rows
- Ensures no data is missed

#### 12. `save_processed_data(...)`
- Saves all processed data as JSON files
- Creates organized directory structure
- Generates comprehensive metadata
- Returns save statistics

#### 13. `copy_original_export(...)`
- Archives original CSV files
- Preserves directory structure
- Allows re-processing if needed

#### 14. `process_linkedin_export()` (Main Flow)
- Orchestrates all tasks
- Handles errors gracefully
- Cleans up temporary files
- Returns comprehensive results

## Directory Structure

```
./backups/local/linkedin/
├── {username}/
│   └── exports/
│       └── {YYYY-MM-DD}/
│           ├── metadata.json              # Export metadata and summary
│           ├── original/                  # Archived original files
│           │   ├── Profile.csv
│           │   ├── Connections.csv
│           │   ├── Messages.csv
│           │   ├── Posts.csv
│           │   ├── Shares.csv
│           │   ├── Reactions.csv
│           │   ├── Endorsements Given.csv
│           │   ├── Endorsements Received.csv
│           │   └── ... (all other files from export)
│           └── processed/                 # Parsed JSON files
│               ├── profile.json           # Profile information
│               ├── connections.json       # Connections list
│               ├── messages.json          # Message history
│               ├── posts.json             # Posts and shares
│               ├── reactions.json         # Reactions to content
│               ├── endorsements.json      # Given and received endorsements
│               └── csv_index.json         # Index of all CSV files
```

## File Formats

### metadata.json
```json
{
  "export_date": "2026-02-10",
  "processed_at": "2026-02-10T15:30:45.123456+00:00",
  "username": "johndoe",
  "workflow_version": "1.0.0",
  "python_version": "3.12.0",
  "zip_metadata": {
    "zip_path": "/path/to/export.zip",
    "zip_size_mb": 45.67,
    "total_files": 23,
    "found_patterns": ["Profile.csv", "Connections.csv", "Messages.csv"]
  },
  "data_summary": {
    "profile": true,
    "connections_count": 567,
    "messages_count": 1234,
    "posts_count": 89,
    "reactions_count": 456,
    "csv_files_indexed": 23
  },
  "saved_files": ["...", "..."]
}
```

### connections.json
```json
{
  "source_file": "Connections.csv",
  "processed_at": "2026-02-10T15:30:45+00:00",
  "connection_count": 567,
  "connections": [
    {
      "First Name": "Jane",
      "Last Name": "Smith",
      "Email Address": "jane@example.com",
      "Company": "Tech Corp",
      "Position": "Software Engineer",
      "Connected On": "01 Jan 2020"
    },
    ...
  ]
}
```

### csv_index.json
```json
{
  "Profile": {
    "file_path": "Profile.csv",
    "file_name": "Profile.csv",
    "processed_at": "2026-02-10T15:30:45+00:00",
    "row_count": 1,
    "columns": ["First Name", "Last Name", "Headline", "Summary", ...],
    "sample_row": { ... }
  },
  "Connections": { ... },
  ...
}
```

## Usage Examples

### Basic Usage
```python
from workflows.cannot_automate.linkedin import process_linkedin_export
from pathlib import Path

result = process_linkedin_export(
    zip_path=Path("./linkedin_export_2026-02-10.zip")
)

print(f"Processed {result['data_summary']['connections_count']} connections")
print(f"Processed {result['data_summary']['posts_count']} posts")
print(f"Data saved to: {result['export_dir']}")
```

### Specify Export Date and Username
```python
result = process_linkedin_export(
    zip_path=Path("./linkedin_export.zip"),
    export_date="2026-02-10",
    username="johndoe",
)
```

### Keep Extracted Files for Debugging
```python
result = process_linkedin_export(
    zip_path=Path("./linkedin_export.zip"),
    keep_extracted=True,  # Don't delete temp directory
)
```

### Custom Output Directory
```python
from pathlib import Path

result = process_linkedin_export(
    zip_path=Path("./linkedin_export.zip"),
    output_dir=Path("/mnt/nas/backups/linkedin"),
)
```

## Idempotency

The workflow is idempotent based on **export_date**:

1. Each export is stored in a date-specific directory: `exports/{YYYY-MM-DD}/`
2. Multiple runs with the same `export_date` will overwrite previous data
3. Different `export_date` values create separate backups
4. This allows tracking changes over time by requesting periodic LinkedIn exports

### Example: Monthly Backups
```python
# February backup
process_linkedin_export(
    zip_path=Path("./linkedin_2026-02-10.zip"),
    export_date="2026-02-10"
)

# March backup
process_linkedin_export(
    zip_path=Path("./linkedin_2026-03-10.zip"),
    export_date="2026-03-10"
)

# Directory structure:
# ./backups/local/linkedin/johndoe/exports/
#   2026-02-10/  <- February data
#   2026-03-10/  <- March data
```

## Error Handling

The workflow includes comprehensive error handling:

1. **Invalid ZIP File**: Validates ZIP before processing
2. **Missing CSV Files**: Gracefully handles missing optional files
3. **CSV Parsing Errors**: Logs errors and continues with other files
4. **Encoding Issues**: Uses UTF-8 encoding with fallback
5. **Disk Space**: May fail if insufficient space for extraction

All errors are logged with context using Prefect's logging system.

## Scheduling Recommendations

Since the download is manual, consider these scheduling strategies:

### 1. Calendar Reminders
Set up monthly/quarterly reminders to:
1. Request LinkedIn data export
2. Wait 24 hours for email
3. Download ZIP file
4. Run workflow script

### 2. Prefect Reminder Flow
Create a separate flow that sends reminder notifications:
```python
from prefect import flow
from prefect.schedules import IntervalSchedule
from datetime import timedelta

@flow(schedule=IntervalSchedule(interval=timedelta(days=30)))
def remind_linkedin_export():
    logger = get_run_logger()
    logger.info("REMINDER: Request LinkedIn data export!")
    logger.info("Go to: Settings & Privacy > Data Privacy > Get a copy of your data")
    # Could send email notification here
```

### 3. Immediate Processing
Once you download the ZIP:
```bash
# Option 1: Direct execution
python workflows/cannot-automate/linkedin.py

# Option 2: Programmatic
python -c "
from workflows.cannot_automate.linkedin import process_linkedin_export
from pathlib import Path
process_linkedin_export(Path('./Downloads/linkedin_export.zip'))
"
```

## Data Privacy Notes

1. **Local Storage**: All data is stored locally (not uploaded anywhere)
2. **Credentials Not Needed**: No LinkedIn credentials required
3. **Archive Original Files**: Original CSVs are preserved for reference
4. **Sensitive Data**: Messages and emails are included; ensure proper access control
5. **Retention Policy**: Consider periodically cleaning old exports if storage is limited

## Limitations

1. **Manual Download Required**: Cannot automate the export request or download
2. **24-Hour Wait**: LinkedIn takes up to 24 hours to prepare export
3. **72-Hour Expiry**: Download link expires after 72 hours
4. **No Real-Time Sync**: Data is only current as of export date
5. **Format Changes**: LinkedIn may change export format without notice (workflow should handle gracefully via CSV indexing)

## Testing

To test the workflow without a real LinkedIn export:

1. **Create Mock CSV Files**:
```python
import csv
from pathlib import Path

# Create mock Profile.csv
profile_data = [{
    "First Name": "John",
    "Last Name": "Doe",
    "Headline": "Software Engineer",
    "Public Profile URL": "https://linkedin.com/in/johndoe"
}]

with open("Profile.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=profile_data[0].keys())
    writer.writeheader()
    writer.writerows(profile_data)

# Similar for Connections.csv, Messages.csv, etc.
```

2. **Create Mock ZIP**:
```python
import zipfile

with zipfile.ZipFile("mock_linkedin_export.zip", "w") as zf:
    zf.write("Profile.csv")
    zf.write("Connections.csv")
    # Add other mock files
```

3. **Run Workflow**:
```python
from workflows.cannot_automate.linkedin import process_linkedin_export

result = process_linkedin_export(
    zip_path=Path("./mock_linkedin_export.zip")
)
```

## Future Enhancements

1. **Diff Detection**: Compare exports across dates to detect:
   - New connections
   - Removed connections
   - Profile changes
   - New messages/posts

2. **Visualization**: Create graphs of:
   - Connection growth over time
   - Post frequency
   - Message statistics

3. **Search Functionality**: Full-text search across:
   - Messages
   - Posts
   - Profile data

4. **Export to Other Formats**:
   - Excel spreadsheets
   - SQLite database
   - Parquet for analytics

5. **Media Download**: Parse and download media files referenced in:
   - Profile pictures
   - Post images/videos
   - Message attachments

## References

- [Download your account data | LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a1339364/downloading-your-account-data)
- [How to Download Your LinkedIn Data Archive](https://blog.closelyhq.com/how-to-download-your-linkedin-data-archive/)
- [LinkedIn Data Export - Typing Post](https://typingpost.com/blog/linkedin-data-export/)
- [LinkedIn ZIP Parser (GitHub)](https://github.com/remixed2/linkedin-zip-parser)
- [LinkedIn API Documentation](https://developer.linkedin.com/product-catalog)
- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-01)
