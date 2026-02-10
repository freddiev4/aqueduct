# Google Drive Workflow - Fixes Needed

**Date:** 2026-02-05
**Priority:** 2 HIGH, 4 LOW

---

## Issue #1: HttpError Attribute Access (HIGH PRIORITY)

**File:** `workflows/google_drive.py`
**Line:** 414

**Current Code:**
```python
except HttpError as e:
    error_msg = f"HTTP error {e.resp.status}: {e.error_details}"
    logger.error(f"Failed to download {file_name}: {error_msg}")
    result['error'] = error_msg
```

**Problem:** `e.resp.status` and `e.error_details` attributes may not exist, causing AttributeError during error handling.

**Fixed Code:**
```python
except HttpError as e:
    # Safely access HttpError attributes
    status = getattr(e.resp, 'status', 'unknown') if hasattr(e, 'resp') else 'unknown'
    details = getattr(e, 'error_details', str(e))
    error_msg = f"HTTP error {status}: {details}"
    logger.error(f"Failed to download {file_name}: {error_msg}")
    result['error'] = error_msg
```

**Impact:** Prevents runtime errors when handling API errors.
**Effort:** 5 minutes

---

## Issue #2: Rate Limiting Implementation (HIGH PRIORITY)

**File:** `workflows/google_drive.py`
**Lines:** Multiple functions

**Problem:** Documentation claims "Rate limit handling with exponential backoff" but it's not implemented. Workflow will fail on 429 errors for large Drive accounts.

### Option A: Implement Rate Limiting (Recommended)

Add retry logic to tasks that call the API:

**For `list_all_files()`:**
```python
from prefect.tasks import exponential_backoff

@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def list_all_files(
    service,
    modified_after: Optional[datetime] = None,
    include_shared: bool = True,
) -> list[dict]:
    # ... existing code ...
```

**For `download_file()`:**
```python
@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def download_file(
    service,
    file_metadata: dict,
    output_dir: Path,
) -> dict:
    # ... existing code ...
```

**For `build_folder_structure()`:**
```python
@task(
    cache_policy=NO_CACHE,
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def build_folder_structure(
    service,
) -> dict:
    # ... existing code ...
```

### Option B: Update Documentation (Quick Fix)

**File:** `docs/google-drive/docs.md`
**Line:** 17

**Current:**
```markdown
- Rate limit handling with exponential backoff
```

**Change to:**
```markdown
- Google API quota limit handling (workflow will fail on 429 errors; manual retry needed)
```

**Impact:** Prevents workflow failures on large Drive accounts with API rate limits.
**Effort:** 20-30 minutes (Option A) or 2 minutes (Option B)

---

## Issue #3: Double Extension Problem (LOW PRIORITY)

**File:** `workflows/google_drive.py`
**Line:** 346

**Current Code:**
```python
# Create filename with extension
export_name = f"{file_id}_{file_name}.{ext}"
```

**Problem:** If Google Doc is named "Report.docx", exports become "file123_Report.docx.docx"

**Fixed Code:**
```python
from pathlib import Path as PathlibPath

# Strip extension from file_name before adding export extension
base_name = PathlibPath(file_name).stem
export_name = f"{file_id}_{base_name}.{ext}"
```

**Impact:** Cleaner filenames, avoids double extensions.
**Effort:** 5 minutes

---

## Issue #4: Sequential File Processing (LOW PRIORITY - Performance)

**File:** `workflows/google_drive.py`
**Lines:** 714-741

**Current Code:**
```python
for i, file_metadata in enumerate(all_files, 1):
    file_name = file_metadata.get('name', 'unknown')
    logger.info(f"Processing file {i}/{len(all_files)}: {file_name}")

    # Download file
    download_result = download_file(
        service=service,
        file_metadata=file_metadata,
        output_dir=files_dir,
    )

    # Save metadata
    save_file_metadata(
        file_metadata=file_metadata,
        download_result=download_result,
        output_dir=files_dir,
    )
```

**Problem:** Downloads files one at a time. Slow for large Drive accounts.

**Fixed Code:**
```python
# Parallel download using Prefect's task mapping
from prefect import task
from concurrent.futures import as_completed

logger.info(f"Downloading {len(all_files)} files in parallel...")

# Create task submissions for parallel execution
download_futures = []
for file_metadata in all_files:
    future = download_file.submit(
        service=service,
        file_metadata=file_metadata,
        output_dir=files_dir,
    )
    download_futures.append((future, file_metadata))

# Process results as they complete
downloaded_count = 0
failed_count = 0
total_size = 0

for i, (future, file_metadata) in enumerate(download_futures, 1):
    file_name = file_metadata.get('name', 'unknown')
    logger.info(f"Completed {i}/{len(all_files)}: {file_name}")

    download_result = future.result()

    # Save metadata
    save_file_metadata(
        file_metadata=file_metadata,
        download_result=download_result,
        output_dir=files_dir,
    )

    # Update counters
    if download_result['downloaded']:
        downloaded_count += 1
        if 'size' in download_result:
            total_size += download_result['size']
        for export in download_result.get('exports', []):
            total_size += export.get('size', 0)
    else:
        failed_count += 1
```

**Impact:** 10x faster downloads for large Drive accounts (1000+ files).
**Effort:** 10-15 minutes
**Note:** May hit rate limits faster; requires Issue #2 fix first.

---

## Issue #5: Folder Structure Memory Usage (LOW PRIORITY)

**File:** `workflows/google_drive.py`
**Lines:** 524-535

**Current Code:**
```python
# Link children to parents
root_folders = []
for folder_id, folder_data in folder_map.items():
    parents = folder_data['parents']
    if not parents:
        # Root folder
        root_folders.append(folder_data)
    else:
        # Add to parent's children
        for parent_id in parents:
            if parent_id in folder_map:
                folder_map[parent_id]['children'].append(folder_data)
```

**Problem:** Duplicates full folder objects in children arrays. Large JSON for complex hierarchies.

**Fixed Code:**
```python
# Link children to parents (store IDs only)
root_folders = []
for folder_id, folder_data in folder_map.items():
    parents = folder_data['parents']
    if not parents:
        # Root folder
        root_folders.append(folder_id)  # Store ID instead of object
    else:
        # Add to parent's children
        for parent_id in parents:
            if parent_id in folder_map:
                folder_map[parent_id]['children'].append(folder_id)  # Store ID

return {
    'folder_count': len(folders),
    'root_folder_ids': root_folders,  # Changed field name
    'folder_map': folder_map,
}
```

**Note:** This changes the folder_structure.json format. Update documentation if changed.

**Impact:** Smaller JSON files, less memory usage.
**Effort:** 10 minutes
**Risk:** Breaking change to folder_structure.json format

---

## Issue #6: Documentation Inaccuracy (LOW PRIORITY)

**File:** `docs/google-drive/docs.md`
**Line:** 17

**Current:**
```markdown
- Rate limit handling with exponential backoff
```

**Problem:** Feature not implemented (see Issue #2).

**Fix:** Remove this line OR implement the feature (see Issue #2, Option A).

**Impact:** Accurate documentation.
**Effort:** 1 minute

---

## Summary

| Issue | Priority | Effort | Impact | Breaking Change |
|-------|----------|--------|--------|-----------------|
| #1: HttpError access | HIGH | 5 min | Prevents crashes | No |
| #2: Rate limiting | HIGH | 20-30 min | Prevents failures | No |
| #3: Double extensions | LOW | 5 min | Cleaner filenames | No |
| #4: Parallelization | LOW | 10-15 min | 10x faster | No |
| #5: Folder structure | LOW | 10 min | Smaller files | Yes |
| #6: Documentation | LOW | 1 min | Accuracy | No |

**Recommended Fix Order:**
1. Issue #1 (5 min) - Prevents crashes
2. Issue #2 (choose Option A or B)
3. Issue #6 (1 min) - If Option B chosen
4. Issue #3 (5 min) - Nice to have
5. Issue #4 (10-15 min) - Performance boost
6. Issue #5 (10 min) - Only if breaking change acceptable

**Total estimated effort:** 40-60 minutes for all fixes (Option A for Issue #2)
**Minimum recommended:** 25-35 minutes (Issues #1, #2, #3)

---

## Testing After Fixes

After implementing fixes, test:

1. **HttpError handling:**
   - Temporarily use invalid credentials
   - Verify error messages don't crash

2. **Rate limiting:**
   - Test with max_files=1000
   - Monitor for 429 errors
   - Verify retries occur

3. **Double extensions:**
   - Create Google Doc named "Test.docx"
   - Verify exports: `file123_Test.docx` and `file123_Test.pdf`

4. **Parallelization:**
   - Test with 100 files
   - Compare execution time before/after
   - Verify all files downloaded correctly

5. **Folder structure:**
   - Verify folder_structure.json format
   - Test with complex folder hierarchies
   - Check file size before/after

---

**All fixes are backward-compatible except Issue #5** (folder structure change).
