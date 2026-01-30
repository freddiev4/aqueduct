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
