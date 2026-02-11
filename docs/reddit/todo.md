# Reddit Workflow - TODO

## Implementation Status

### Completed ✅

- [x] Create RedditBlock for credentials storage
- [x] Implement main workflow (`workflows/reddit.py`)
- [x] Add OAuth2 authentication with PRAW
- [x] Implement saved posts fetching
- [x] Implement comments history fetching
- [x] Implement upvoted content fetching
- [x] Add media download support (images, videos)
- [x] Implement idempotency with snapshot dates
- [x] Use Reddit IDs for filenames (t3_xxx, t1_xxx)
- [x] Maintain download archive for media
- [x] Sort API results deterministically
- [x] Use UTC timezone for all timestamps
- [x] Add comprehensive error handling
- [x] Add detailed logging
- [x] Create backup manifests
- [x] Write setup documentation
- [x] Write implementation plan
- [x] Write technical documentation
- [x] Add example usage in `__main__` block
- [x] Update TODO.md

### Testing Needed 🧪

- [ ] Test with real Reddit account
- [ ] Verify authentication flow
- [ ] Test saved posts backup
- [ ] Test comments backup
- [ ] Test upvoted content backup
- [ ] Test media downloads (images)
- [ ] Test media downloads (videos)
- [ ] Test idempotency (run twice with same date)
- [ ] Verify download archive works correctly
- [ ] Test with 2FA-enabled account
- [ ] Test error handling (invalid credentials)
- [ ] Test with empty saved/upvoted lists
- [ ] Test with limit parameter
- [ ] Verify directory structure
- [ ] Check JSON metadata format

### Future Enhancements 🔮

- [ ] **Gallery support**: Download all images from gallery posts
- [ ] **Video quality options**: Allow selecting video quality
- [ ] **Incremental backups**: Only fetch new content since last backup
- [ ] **Filter by subreddit**: Backup only specific subreddits
- [ ] **Filter by date range**: Backup content from specific time period
- [ ] **Submission attachments**: Download linked content (PDFs, etc.)
- [ ] **Comment threading**: Preserve comment thread structure
- [ ] **User profile data**: Backup profile info, karma, trophies
- [ ] **Private messages**: Backup Reddit PMs (if API allows)
- [ ] **Multireddit backup**: Backup custom multireddit configurations
- [ ] **RES tags**: Export Reddit Enhancement Suite tags (if applicable)
- [ ] **Search functionality**: Build search index over backed up content
- [ ] **Export formats**: Support exporting to CSV, HTML
- [ ] **Compression**: Option to compress old backups
- [ ] **Prefect deployment**: Create scheduled deployment config

## Known Limitations

1. **Reddit API limits**: Maximum ~1000 items per listing (Reddit limitation)
2. **Gallery images**: Individual image extraction not yet implemented
3. **Deleted content**: Cannot retrieve deleted posts/comments
4. **Private content**: Requires appropriate permissions
5. **Rate limits**: Large backups may take significant time
6. **Media expiration**: Some media URLs may expire over time

## Dependencies

All dependencies already in `pyproject.toml`:
- praw>=7.7.1
- requests>=2.31.0
- prefect>=3.5.0
- python-dotenv>=1.2.1

## Next Steps

1. **Immediate**: Test with real Reddit account
2. **Short-term**: Verify idempotency and media downloads
3. **Medium-term**: Create Prefect deployment for scheduled backups
4. **Long-term**: Implement gallery support and incremental backups
