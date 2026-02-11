# LinkedIn Workflow Implementation Plan

**Date:** 2026-02-10
**Status:** Research & Planning

## Executive Summary

After researching LinkedIn's API capabilities, I've determined that creating an automated LinkedIn backup workflow faces significant challenges. LinkedIn's official APIs are highly restricted and require partnership approval, making true automation difficult without violating terms of service.

## Research Findings

### LinkedIn Official API Status

1. **API Access Restrictions** (2026)
   - LinkedIn removed public API access in 2015
   - Current API access requires approval as a LinkedIn Partner
   - Even with approval, significant rate limits and caps apply
   - Access to personal data (profile, connections, messages) is heavily restricted

2. **Available Official APIs**
   - **Profile API**: Requires partnership, limited to approved use cases
   - **Connections API**: Highly restricted to prevent spam
   - **Posts API**: Available but requires OAuth 2.0 and partnership approval
   - **Messages API**: Not accessible without special partnership status

3. **Member Portability APIs** (GDPR Compliance)
   - LinkedIn provides "Member Portability APIs" for EU/EEA/Switzerland members
   - Designed for GDPR data portability requirements
   - Requires explicit user consent and partnership approval
   - Not available for general automation use

### LinkedIn Data Export (Manual Process)

LinkedIn provides a native data export feature:
- Access via Settings & Privacy > Data Privacy > "Get a copy of your data"
- Supports full archive or selective categories
- Archive delivered as ZIP with CSV/JSON files within 24 hours
- Available for download for 72 hours
- **This is a manual process** - no API for automating the download request

### Automation Alternatives

1. **Unofficial Python Libraries**
   - `linkedin-api` (PyPI): Uses LinkedIn's internal Voyager API
   - `linkedin_scraper`: Browser-based scraping with Selenium
   - **Risk**: Violates LinkedIn's Terms of Service
   - **Risk**: Account suspension or permanent ban
   - **Risk**: Unreliable due to LinkedIn's anti-bot measures

2. **Selenium/Browser Automation**
   - Can automate login and navigation to export page
   - LinkedIn detects automated logins and requests email verification
   - Advanced fingerprinting and behavioral detection
   - High risk of account restrictions

3. **Third-Party Services**
   - Coefficient, Stevesie, MagicalAPI offer LinkedIn data export
   - Require their own authentication and subscription
   - May violate LinkedIn ToS
   - Not suitable for personal backup use case

## Recommendation

**LinkedIn workflow should be placed in `workflows/cannot-automate/` directory.**

### Reasons:

1. **No official automation path**: LinkedIn's APIs require partnership approval not available to individual users
2. **ToS violations**: Unofficial libraries and scraping violate LinkedIn's Terms of Service
3. **Account risk**: Automation attempts risk account suspension
4. **Detection mechanisms**: LinkedIn has sophisticated anti-automation defenses
5. **Manual process**: Official data export requires human interaction (24-hour wait, download link)

### Alternative Solution: Semi-Manual Workflow

Instead of full automation, I recommend creating a **helper workflow** that:

1. **Guides users through the manual export process**
   - Instructions for requesting data export from LinkedIn
   - Monitoring for the email notification
   - Helper script to download and organize the ZIP file once available

2. **Automates post-download processing**
   - Extracts ZIP file
   - Parses CSV/JSON files
   - Organizes into aqueduct's standard structure
   - Creates searchable metadata
   - Tracks export history

3. **Scheduled reminders**
   - Prefect flow that reminds users to run manual export (e.g., monthly)
   - No actual LinkedIn API interaction
   - Just local file processing after manual download

## Implementation Options

### Option A: Cannot-Automate (Recommended)
- Create workflow in `workflows/cannot-automate/linkedin.py`
- Document why automation isn't possible
- Provide manual export instructions
- Include post-download processing script

### Option B: Semi-Automated Helper
- Create workflow in `workflows/linkedin.py`
- Implements post-download ZIP processing only
- Includes detailed manual export guide
- Prefect flow for reminder scheduling

### Option C: Risk-Accepting Unofficial Approach (NOT RECOMMENDED)
- Use `linkedin-api` or Selenium
- Implement aggressive anti-detection measures
- Accept ToS violation risk
- Document account suspension risk clearly
- Should be in `cannot-automate/` with strong warnings

## Proposed Implementation (Option A)

Create a documentation-focused workflow that:

1. **Documents the manual process** clearly
2. **Provides a post-processing script** for downloaded exports
3. **Stores exports** in standard aqueduct structure:
   ```
   ./backups/local/linkedin/{username}/
     exports/
       2026-02-10/
         Basic_LinkedInDataExport_02-10-2026/  (extracted ZIP)
         metadata.json
         processed/
           profile.json
           connections.json
           messages.json
           posts.json
   ```
4. **Creates searchable metadata** from CSV/JSON files
5. **Tracks export history** to avoid duplicate processing

## Next Steps

1. Confirm approach with user (Option A recommended)
2. Create workflow in `workflows/cannot-automate/linkedin.py`
3. Implement ZIP extraction and CSV/JSON parsing
4. Create README documenting manual export process
5. Test with sample LinkedIn data export

## Sources

Research based on:
- [LinkedIn API Documentation - Microsoft Learn](https://learn.microsoft.com/en-us/linkedin/)
- [What Is LinkedIn API? Complete Guide On How It Works [2026]](https://evaboot.com/blog/what-is-linkedin-api)
- [Download your account data | LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a1339364/downloading-your-account-data)
- [Member portability APIs | LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a6214075)
- [linkedin-api · PyPI](https://pypi.org/project/linkedin-api/)
- [How to Scrape LinkedIn in 2026](https://scrapfly.io/blog/posts/how-to-scrape-linkedin)
- [Posts API - LinkedIn | Microsoft Learn](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-01)

## Decision Required

**Please confirm which approach you'd like to proceed with:**
- **Option A**: Cannot-automate workflow with manual export documentation (RECOMMENDED)
- **Option B**: Semi-automated helper with post-download processing
- **Option C**: Risk-accepting unofficial approach (NOT RECOMMENDED)
