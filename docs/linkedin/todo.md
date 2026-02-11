# LinkedIn Workflow - TODO

## Completed Tasks

- [x] Research LinkedIn API capabilities and limitations
- [x] Confirm that automation is not possible without ToS violations
- [x] Design workflow for post-download processing
- [x] Create `workflows/cannot-automate/linkedin.py` with full implementation
- [x] Update `workflows/cannot-automate/README.md` with LinkedIn documentation
- [x] Implement ZIP validation and extraction
- [x] Implement CSV parsing for all major data types (Profile, Connections, Messages, Posts, Reactions, Endorsements)
- [x] Implement comprehensive CSV file indexing
- [x] Create organized directory structure for backups
- [x] Add metadata generation and tracking
- [x] Archive original files alongside processed data
- [x] Add UTC timezone consistency throughout
- [x] Follow all aqueduct patterns (task-based design, NO_CACHE, proper error handling)
- [x] Create documentation in plan.md and docs.md

## Optional Enhancements (Future)

- [ ] Add support for parsing HTML files from LinkedIn export
- [ ] Create visualization tools for connections graph
- [ ] Implement diff detection between multiple exports
- [ ] Add search functionality across processed data
- [ ] Create summary statistics dashboard
- [ ] Add support for parsing media files (images from posts)
- [ ] Implement data validation and quality checks
- [ ] Add unit tests for CSV parsing functions
- [ ] Create integration tests with sample LinkedIn export data

## Notes

Since LinkedIn blocks are not needed (no API authentication), we don't need to create `blocks/linkedin_block.py`. The workflow operates entirely on downloaded ZIP files.

If in the future LinkedIn provides automatable APIs, we would need to:
1. Create `blocks/linkedin_block.py` for credentials
2. Add LinkedIn credentials to `.env.example`
3. Move workflow to main `workflows/` directory
4. Implement API-based data fetching
