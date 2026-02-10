# Workflows That Cannot Be Automated

This directory contains workflows that are not functional due to API restrictions or policy changes that prevent automated access.

## Google Photos (`google_photos.py`)

**Status:** Broken as of April 1, 2025

### What Happened

Google deprecated the broad Library API scopes on March 31, 2025:

| Deprecated Scope | Purpose |
|------------------|---------|
| `photoslibrary.readonly` | Read access to user's entire photo library |
| `photoslibrary.sharing` | Access to shared albums |
| `photoslibrary` | Full read/write access to library |

### Current API Limitations

The only remaining Library API scopes are:

| Scope | Purpose |
|-------|---------|
| `photoslibrary.appendonly` | Upload only - cannot read anything |
| `photoslibrary.readonly.appcreateddata` | Read only content YOUR app uploaded |
| `photoslibrary.edit.appcreateddata` | Edit only content YOUR app uploaded |

**You can no longer programmatically list, search, or download a user's existing photos.**

### Why This Breaks Automated Backups

1. The `mediaItems().list()` API call requires the deprecated `photoslibrary.readonly` scope
2. New scopes only allow access to photos your application created/uploaded
3. There is no way to enumerate or download a user's existing photo library

### Alternatives

1. **Google Takeout** - Manual export from https://takeout.google.com
   - Pros: Gets entire library, official Google method
   - Cons: Manual process, not automatable

2. **Picker API** - New Google-sanctioned method for photo access
   - Pros: Works with current API
   - Cons: Requires user to manually select photos through Google's UI each time, not suitable for automated backups

3. **Third-party tools** (e.g., gphotos-sync using browser automation)
   - Pros: May still work
   - Cons: Violates Google ToS, may break at any time, account risk

### References

- [Google Photos API Authorization Scopes](https://developers.google.com/photos/overview/authorization)
- [Google Photos API Updates Blog Post](https://developers.googleblog.com/en/google-photos-picker-api-launch-and-library-api-updates/)
- [Community discussion on rclone](https://github.com/rclone/rclone/issues/8567)

## iCloud (`icloud.py`)

**Status:** Cannot fully automate (researched February 2026)

### Summary

Apple does not provide a general-purpose public API for accessing iCloud account data. All programmatic access relies on either reverse-engineered web APIs (which Apple can break at any time) or local macOS database files. iMessages are not accessible via any web API at all.

### What CAN Be Accessed Programmatically

| Data Type | Method | Fully Automated? | Notes |
|-----------|--------|-------------------|-------|
| **Contacts** | CardDAV protocol (`contacts.icloud.com`) | Yes | App-specific password, no recurring 2FA |
| **Calendars** | CalDAV protocol (`caldav.icloud.com`) | Yes | App-specific password, no recurring 2FA |
| **Photos** | [icloudpd](https://github.com/icloud-photos-downloader/icloud_photos_downloader) (reverse-engineered web API) | Semi | Needs manual 2FA re-auth every ~2 months |
| **iCloud Drive** | [pyicloud](https://github.com/timlaing/pyicloud) (timlaing fork) | Semi | Same 2FA constraint |
| **Reminders** | pyicloud reminders service | Semi | Limited data access |
| **iMessages** | Local macOS `~/Library/Messages/chat.db` | Yes (macOS only) | Requires Full Disk Access permission |
| **Notes** | Local macOS `~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite` | Yes (macOS only) | Complex binary format parsing |

### What CANNOT Be Accessed

- **iMessages via iCloud API** — Not exposed through any web service whatsoever
- **Notes (structured) via iCloud API** — No dedicated Notes API exists
- **Any data when Advanced Data Protection (ADP) is enabled** — Encryption keys only exist on trusted devices; fundamentally incompatible with all third-party tools
- **Health data, Keychain, Mail** — Not exposed through pyicloud or any known interface

### Why This Can't Be Fully Automated

1. **Mandatory 2FA with session expiry**: Every iCloud web API approach (pyicloud, icloudpd) requires human interaction to enter a 2FA code when the session expires (~every 2 months). There is no way around this.

2. **Apple broke all tools in October 2024**: Apple switched iCloud authentication to the SRP-6a (Secure Remote Password) protocol, which broke every pyicloud-based tool. The `timlaing/pyicloud` fork implemented a fix, but this demonstrates Apple can (and will) break reverse-engineered access without notice.

3. **Apple ToS explicitly prohibits automated access**: Apple's terms prohibit "any 'deep-link', 'page-scrape', 'robot', 'spider' or other automatic device" to access their services. No known account bans so far, but no guarantees.

4. **Undocumented rate limiting**: Apple throttles requests aggressively with 503 errors. icloudpd recommends minimum 1-hour intervals between syncs. No official documentation on limits exists.

### Key Libraries

| Library | Status | What It Accesses |
|---------|--------|------------------|
| [icloudpd](https://github.com/icloud-photos-downloader/icloud_photos_downloader) (v1.32.2+) | Active | iCloud Photos |
| [pyicloud (timlaing fork)](https://github.com/timlaing/pyicloud) (v2.3.0+) | Active, used by Home Assistant | Photos, Contacts, Calendar, iCloud Drive, Find My, Reminders |
| [pyicloud (original)](https://github.com/picklepete/pyicloud) | Largely stale since 2022 | Same as above but many unmerged fixes |
| [imessage-exporter](https://github.com/ReagentX/imessage-exporter) | Active (Rust CLI) | Local macOS `chat.db` for iMessages |
| [pymessage-lite](https://github.com/mattrajca/pymessage-lite) | Python | Local macOS `chat.db` |
| [apple_cloud_notes_parser](https://github.com/threeplanetssoftware/apple_cloud_notes_parser) | Active | Local macOS Notes SQLite database |

### iMessage-Specific Notes

Since the user specifically asked about dumping texts:

- iMessages are **never** exposed through iCloud web services. Apple considers them end-to-end encrypted.
- On macOS, messages are stored in `~/Library/Messages/chat.db` (SQLite). This is the only programmatic access path.
- Requires **Full Disk Access** permission (since macOS Mojave) for any process reading the database.
- Starting with macOS Ventura, message content moved from plain text to hex-encoded blobs in the `attributedBody` column, requiring additional parsing.
- A fully automated ETL pipeline using `imessage-exporter` + macOS LaunchAgent for daily exports has been [documented](https://albahra.com/2024/08/creating-an-etl-for-apple-imessages-a-comprehensive-guide).
- iPhone backup extraction is also possible (parse `chat.db` from an iTunes/Finder backup) but is not easily scheduled.

### Alternatives

1. **Apple's Data & Privacy Portal** (https://privacy.apple.com) — Manual GDPR-compliant export of photos, contacts, calendars, etc. Takes up to a week, downloads expire in 2 weeks. **iMessages are explicitly excluded** because they are end-to-end encrypted.

2. **CalDAV/CardDAV for Contacts & Calendars** — This is the one legitimately automatable path. Uses standard protocols with app-specific passwords (no recurring 2FA). Could potentially be a standalone `workflows/icloud_caldav.py`.

3. **macOS Local Database Access** — If running on a Mac with iCloud sync, a workflow could read local SQLite databases for iMessages and Notes. Fully automatable but macOS-only and requires Full Disk Access.

### Recommendation

- **Contacts + Calendars via CalDAV/CardDAV**: Could be a real automated workflow (`workflows/icloud_caldav.py`) since they use standard protocols with app-specific passwords.
- **Everything else**: Stays in `cannot-automate/` due to 2FA requirements, API fragility, and ToS concerns.
- **iMessages**: Only possible on macOS via local `chat.db`. If the deployment target is a Mac, a local-only workflow is viable.

### References

- [picklepete/pyicloud](https://github.com/picklepete/pyicloud)
- [timlaing/pyicloud](https://github.com/timlaing/pyicloud)
- [icloud-photos-downloader/icloud_photos_downloader](https://github.com/icloud-photos-downloader/icloud_photos_downloader)
- [iCloud integration SRP-6a breakage — Home Assistant Issue #128830](https://github.com/home-assistant/core/issues/128830)
- [ReagentX/imessage-exporter](https://github.com/ReagentX/imessage-exporter)
- [Creating an ETL for Apple iMessages — Samer Albahra](https://albahra.com/2024/08/creating-an-etl-for-apple-imessages-a-comprehensive-guide)
- [Apple iCloud Terms of Service](https://www.apple.com/legal/internet-services/icloud/)
- [Apple Data & Privacy Portal](https://privacy.apple.com/)
- [iCloud throttling — The Eclectic Light Company](https://eclecticlight.co/2024/02/22/icloud-does-throttle-data-syncing-after-all/)
- [Apple CloudKit Developer Documentation](https://developer.apple.com/icloud/cloudkit/)

## LinkedIn (`linkedin.py`)

**Status:** Cannot fully automate (researched February 2026)

### Summary

LinkedIn removed public API access in 2015. Current APIs require LinkedIn Partner approval which is not available to individual users. The only way to obtain your LinkedIn data is through their manual GDPR-compliant data export feature, which takes 24 hours to process and requires manual download.

### Why This Can't Be Automated

1. **No Public API Access**: LinkedIn shut down public API access in 2015. Current APIs are only available to approved LinkedIn Partners.

2. **Restricted API Scopes**: Even with partnership, APIs for personal data (profile, connections, messages) are heavily restricted to prevent spam and protect user privacy.

3. **Manual Export Only**: LinkedIn's data export feature requires:
   - Manual initiation from Settings & Privacy
   - 24-hour processing time
   - Manual download from email link (expires in 72 hours)
   - No API endpoint to automate the request or download

4. **Unofficial Methods Violate ToS**: Libraries like `linkedin-api` (uses internal Voyager API) and Selenium automation explicitly violate LinkedIn's Terms of Service and risk account suspension.

5. **Advanced Anti-Bot Detection**: LinkedIn employs sophisticated fingerprinting, behavioral detection, and email verification to block automated access.

### What This Workflow Does

Since full automation isn't possible, this workflow provides **post-download processing**:

1. **Accepts a downloaded LinkedIn export ZIP file** (manually obtained)
2. **Extracts and validates** the ZIP contents
3. **Parses all CSV files** (Profile, Connections, Messages, Posts, Reactions, Endorsements, etc.)
4. **Organizes data** into searchable JSON format
5. **Creates metadata** for easy querying
6. **Archives original files** for reference

### Directory Structure

```
./backups/local/linkedin/
  {username}/
    exports/
      {YYYY-MM-DD}/
        original/              # Archived original CSV/JSON files
          Profile.csv
          Connections.csv
          Messages.csv
          ...
        processed/             # Parsed and organized JSON files
          profile.json
          connections.json
          messages.json
          posts.json
          reactions.json
          endorsements.json
          csv_index.json      # Index of all CSV files found
        metadata.json         # Export metadata and summary
```

### How to Use

1. **Request LinkedIn Data Export**:
   - Go to Settings & Privacy > Data Privacy > "Get a copy of your data"
   - Select "Fast" (selected data) or "Complete" (full archive)
   - Choose data types (recommend selecting all)
   - Click "Request archive"

2. **Wait for Email**: LinkedIn will email you when the export is ready (typically within 24 hours)

3. **Download ZIP File**: Click the link in the email to download (link expires in 72 hours)

4. **Run Workflow**:
   ```python
   from workflows.cannot_automate.linkedin import process_linkedin_export
   from pathlib import Path

   result = process_linkedin_export(
       zip_path=Path("./path/to/linkedin_export.zip"),
       export_date=None,  # Auto-uses today's date
       username=None,     # Auto-detected from export
   )
   ```

5. **Access Processed Data**: Find your organized data in `./backups/local/linkedin/{username}/exports/{date}/`

### Data Types Supported

The workflow automatically detects and processes all available CSV files, including:

- **Profile Information**: Basic profile data, headline, summary
- **Connections**: All 1st-degree connections with connection dates
- **Messages**: Complete message history
- **Posts & Shares**: Your published content
- **Reactions**: Posts/comments you've reacted to
- **Comments**: Your comment history
- **Endorsements**: Given and received skill endorsements
- **Recommendations**: Given and received recommendations
- **Invitations**: Sent and received connection invitations
- **Contacts**: Contact list (if available)
- **Articles**: Published long-form articles
- **Learning**: Completed LinkedIn Learning courses
- **Job Applications**: Saved answers and application history

The workflow also creates a comprehensive CSV index for any files not explicitly processed.

### Scheduling Regular Backups

While the download is manual, you can set up reminders:

1. **Calendar Reminder**: Set monthly/quarterly reminders to request LinkedIn export
2. **Process Immediately**: Run the workflow script as soon as you download the ZIP
3. **Track History**: The workflow preserves all exports by date, allowing you to track changes over time

### Alternatives Considered

| Method | Automated? | Issues |
|--------|-----------|--------|
| **Official LinkedIn APIs** | No | Requires partnership approval, not available to individuals |
| **Member Portability APIs** | No | GDPR-compliant but still requires partnership + manual consent |
| **linkedin-api (PyPI)** | Yes | Violates ToS, uses internal Voyager API, risk of account ban |
| **Selenium Automation** | Semi | Triggers email verification, detected as bot, violates ToS |
| **Manual Export + Processing** | Semi | ✓ ToS compliant, reliable, this is what we implement |

### Why Manual Export Is Actually Good

1. **ToS Compliant**: Uses LinkedIn's official data export feature
2. **Complete Data**: Gets everything LinkedIn has on you
3. **No Account Risk**: Zero risk of suspension or ban
4. **Reliable**: Not affected by LinkedIn's API changes or anti-bot measures
5. **GDPR Compliant**: LinkedIn is legally required to provide this
6. **Quality Controlled**: LinkedIn ensures data completeness and accuracy

### References

- [Download your account data | LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a1339364/downloading-your-account-data)
- [LinkedIn API Products](https://developer.linkedin.com/product-catalog)
- [Getting Access to LinkedIn APIs](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access)
- [LinkedIn Posts API Documentation](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-01)
- [How to Download Your LinkedIn Data Archive](https://blog.closelyhq.com/how-to-download-your-linkedin-data-archive/)
- [LinkedIn Data Export - Typing Post](https://typingpost.com/blog/linkedin-data-export/)
- [linkedin-api · PyPI](https://pypi.org/project/linkedin-api/) (unofficial, not recommended)
