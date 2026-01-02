import asyncio
import subprocess
import shutil
import time
import json

from datetime import datetime, timezone, timedelta
from pathlib import Path

from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from prefect.logging import get_run_logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from blocks.github_block import GitHubBlock
from prefect_github.repository_owner import query_repository_owner_repositories
from prefect_github.repository import query_repository
from prefect_github import GitHubCredentials


@task(cache_policy=NO_CACHE)
def get_all_repositories(
    owner: str,
    github_credentials: GitHubCredentials
) -> list[dict]:
    """
    Get all repositories for a given owner with necessary fields for cloning.
    Returns repositories sorted by name for deterministic ordering.
    """
    logger = get_run_logger()

    # Query repositories - specify fields we want on each repository node
    # The library will automatically include nodes when we specify return_fields
    # Note: We don't include "owner" because it causes issues with nested repository queries
    # Note: query_repository_owner_repositories is async, so we use asyncio.run()
    # Add retry logic for transient API errors (like 502 Bad Gateway)
    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            # NOTE: is_fork field causes issues with prefect_github library
            # We'll check fork status another way after fetching the repos
            repositories = asyncio.run(
                query_repository_owner_repositories(
                    login=owner,
                    github_credentials=github_credentials,
                    first=100,  # Get up to 100 repositories per page
                    return_fields=["name", "url", "is_private"]
                )
            )
            # Success, exit retry loop
            break
        except RuntimeError as e:
            error_msg = str(e)
            # Check if it's a 502 or other transient error
            if "502" in error_msg or "Bad Gateway" in error_msg:
                if attempt < max_retries - 1:
                    logger.warning(f"GitHub API returned 502 error, retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(f"GitHub API error after {max_retries} attempts: {error_msg}")
                    raise
            else:
                # Not a transient error, re-raise immediately
                raise

    # Extract repository information
    repo_list = []
    repos_data = repositories.get("nodes", [])

    for repo in repos_data:
        repo_url = repo.get("url", "")
        # Ensure clone_url ends with .git
        clone_url = repo_url if repo_url.endswith(".git") else f"{repo_url}.git"

        # Default branch - we don't query it to avoid permission issues
        # Most repos use "main" or "master", default to "main"
        default_branch = "main"

        # Use the owner parameter we already have (since we're querying by owner)
        owner_login = owner

        # Note: is_fork field removed from query due to library bug
        # Will be detected later by checking repository description/metadata
        repo_list.append({
            "name": repo.get("name"),
            "url": repo_url,
            "clone_url": clone_url,
            "is_private": repo.get("is_private", False),
            "is_fork": False,  # Will be updated after cloning if needed
            "default_branch": default_branch,
            "owner": owner_login
        })

    # Sort repositories by name for deterministic ordering
    repo_list.sort(key=lambda r: r["name"])

    logger.info(f"Found {len(repo_list)} repositories for {owner}")
    logger.info(f"Repositories: {[repo['name'] for repo in repo_list]}")

    return repo_list


@task()
def get_repository_commits(
    owner: str,
    repo_name: str,
    github_credentials: GitHubCredentials,
    until_date: datetime = None,
    max_commits: int = 100
) -> list[dict]:
    """
    Get commits for a repository up until a specific date using GitHub GraphQL API.

    Uses the Prefect GitHub integration's query_repository function to fetch
    commit history from the repository's default branch.

    Args:
        owner: The repository owner (username or organization)
        repo_name: The repository name
        github_credentials: GitHub credentials for authentication
        until_date: Optional datetime to filter commits up to this date
        max_commits: Maximum number of commits to retrieve (default: 100)

    Returns:
        List of commit dictionaries with keys: sha, message, author_name,
        author_email, date, url
    """
    try:
        # Query repository with default branch ref and commit history
        # The return_fields format follows GitHub GraphQL API field names in snake_case
        # Note: query_repository is async, so we use asyncio.run()
        result = asyncio.run(
            query_repository(
                owner=owner,
                name=repo_name,
                github_credentials=github_credentials,
                return_fields=[
                    "default_branch_ref",
                    "default_branch_ref.target",
                    "default_branch_ref.target.history",
                ]
            )
        )

        commits = []

        # Extract commits from the GraphQL response
        # Structure: repository -> default_branch_ref -> target -> history -> edges -> node
        default_branch_ref = result.get("default_branch_ref")
        if not default_branch_ref:
            return commits

        target = default_branch_ref.get("target", {})
        if not target:
            return commits

        history = target.get("history", {})
        edges = history.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})
            if not node:
                continue

            # Extract commit information
            commit_date_str = node.get("committed_date") or node.get("author", {}).get("date", "")

            # Parse commit date if available
            commit_date = None
            if commit_date_str:
                try:
                    # GitHub returns ISO 8601 format dates (e.g., "2024-01-01T00:00:00Z")
                    commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Filter by until_date if provided
            if until_date and commit_date:
                # Ensure both dates are timezone-aware for comparison
                if until_date.tzinfo is None:
                    until_date = until_date.replace(tzinfo=timezone.utc)
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=timezone.utc)

                # Skip commits after until_date
                if commit_date > until_date:
                    continue

            author = node.get("author", {})
            commits.append({
                "sha": node.get("oid", ""),
                "message": node.get("message", ""),
                "author_name": author.get("name", ""),
                "author_email": author.get("email", ""),
                "date": commit_date_str,
                "url": node.get("url", ""),
            })

            # Limit number of commits
            if len(commits) >= max_commits:
                break

        return commits

    except Exception as e:
        # Log error and return empty list
        logger = get_run_logger()
        logger.error(f"Error fetching commits for {owner}/{repo_name}: {e}")
        return []


@task(cache_policy=NO_CACHE)
def clone_repository_to_local(
    repo_info: dict,
    github_credentials: GitHubCredentials,
    snapshot_date: datetime,
    local_backup_dir: Path = Path("./backups/local")
) -> Path:
    """
    Clone a repository to the local filesystem with full history.
    Uses timestamped directory structure for non-destructive backups.
    Organizes repos into subdirectories: forks/, private/, or public/
    Note: Removes --depth 1 to enable commit history queries.
    """
    logger = get_run_logger()
    local_backup_dir.mkdir(parents=True, exist_ok=True)

    # Determine category: forks take priority, then private/public
    if repo_info.get("is_fork", False):
        category = "forks"
    elif repo_info.get("is_private", False):
        category = "private"
    else:
        category = "public"

    # NEW: Timestamped directory structure with platform prefix
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    repo_path = (
        local_backup_dir
        / "github"  # Platform prefix
        / repo_info["owner"]
        / "repositories"  # Content type
        / snapshot_str  # Snapshot date
        / category
        / repo_info["name"]
    )

    # Check if this snapshot already exists (idempotency)
    if repo_path.exists():
        logger.info(f"Repository {repo_info['name']} already backed up for snapshot {snapshot_str}, skipping clone...")
        return repo_path

    # Create parent directories
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone the repository
    clone_url = repo_info["clone_url"]

    # If private repo, use token in URL
    if repo_info["is_private"]:
        token = github_credentials.token.get_secret_value()
        # Format: https://token@github.com/owner/repo.git
        clone_url = clone_url.replace("https://", f"https://{token}@")

    try:
        # FIXED: Removed --depth 1 to enable full commit history queries
        subprocess.run(
            ["git", "clone", clone_url, str(repo_path)],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Successfully cloned {repo_info['name']} to {repo_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error cloning {repo_info['name']}: {e.stderr}")
        raise

    return repo_path


@task()
def get_commits_from_local_repo(
    repo_path: Path,
    until_date: datetime = None
) -> list[dict]:
    """
    Get commits from a locally cloned repository using git log.
    Uses full ISO timestamp format for precise date filtering.
    """
    try:
        if until_date:
            # Ensure until_date is UTC-aware
            if until_date.tzinfo is None:
                until_date = until_date.replace(tzinfo=timezone.utc)
            elif until_date.tzinfo != timezone.utc:
                # Convert to UTC if it's in a different timezone
                until_date = until_date.astimezone(timezone.utc)

            # FIXED: Use full timestamp format with explicit time for precise boundary
            date_str = until_date.strftime("%Y-%m-%d %H:%M:%S")
            result = subprocess.run(
                ["git", "-C", str(repo_path), "log", f"--until={date_str}",
                 "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso-strict"],
                capture_output=True,
                text=True,
                check=True
            )
        else:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "log",
                 "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso-strict"],
                capture_output=True,
                text=True,
                check=True
            )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash": parts[0],
                        "author_name": parts[1],
                        "author_email": parts[2],
                        "date": parts[3],
                        "message": parts[4]
                    })

        return commits

    except subprocess.CalledProcessError as e:
        # Provide detailed error information for git failures
        logger = get_run_logger()
        error_msg = f"git log failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        logger.error(f"Error getting commits from {repo_path}: {error_msg}")
        raise RuntimeError(error_msg) from e


# @task()
# def backup_to_remote_filesystem(
#     local_repo_path: Path,
#     remote_backup_dir: Path = Path("./backups/remote")
# ) -> Path:
#     """
#     Copy the local repository backup to a remote filesystem (e.g., NAS).
#     """
#     remote_backup_dir.mkdir(parents=True, exist_ok=True)

#     # Determine the relative path structure
#     # Assuming local_repo_path is like: ./backups/local/owner/repo
#     relative_parts = local_repo_path.parts[-2:]  # owner and repo name
#     remote_repo_path = remote_backup_dir / relative_parts[0] / relative_parts[1]

#     # Remove existing directory if it exists
#     if remote_repo_path.exists():
#         shutil.rmtree(remote_repo_path)

#     # Copy the entire directory
#     shutil.copytree(local_repo_path, remote_repo_path)

#     print(f"Successfully backed up {local_repo_path.name} to {remote_repo_path}")
#     return remote_repo_path


@task()
def check_snapshot_exists(
    owner: str,
    snapshot_date: datetime,
    local_backup_dir: Path = Path("./backups/local")
) -> bool:
    """
    Check if a snapshot already exists for the given date.
    Returns True if both the snapshot directory and manifest exist.
    """
    logger = get_run_logger()
    snapshot_str = snapshot_date.strftime("%Y-%m-%d")
    snapshot_dir = local_backup_dir / "github" / owner / "repositories" / snapshot_str
    manifest_path = local_backup_dir / "github" / owner / "repositories" / f"backup_manifest_{snapshot_str}.json"

    if snapshot_dir.exists() and manifest_path.exists():
        logger.info(f"Snapshot for {snapshot_str} already exists at {snapshot_dir}")
        return True
    return False


@task()
def process_repository(
    repo_info: dict,
    github_credentials: GitHubCredentials,
    until_date: datetime,
    local_backup_dir: Path = Path("./backups/local"),
) -> dict:
    """
    Process a single repository: clone, get commits, and backup.

    Args:
        repo_info: Repository information dictionary
        github_credentials: GitHub credentials for authentication
        until_date: Cutoff date for commit history (required for idempotency)
        local_backup_dir: Base directory for backups

    Returns:
        Dictionary with repository backup statistics
    """
    # FIXED: until_date is now required (no default datetime.now())
    # Validate that until_date is timezone-aware
    if until_date.tzinfo is None:
        until_date = until_date.replace(tzinfo=timezone.utc)

    # Clone to local filesystem
    local_path = clone_repository_to_local(
        repo_info=repo_info,
        github_credentials=github_credentials,
        snapshot_date=until_date,
        local_backup_dir=local_backup_dir,
    )

    # FIXED: Corrected parameter name from local_path to repo_path
    commits = get_commits_from_local_repo(
        repo_path=local_path,
        until_date=until_date,
    )

    # Save per-repository metadata
    repo_metadata = {
        "repo_name": repo_info["name"],
        "repo_url": repo_info.get("url", ""),
        "is_fork": repo_info.get("is_fork", False),
        "is_private": repo_info.get("is_private", False),
        "snapshot_date": until_date.isoformat(),
        "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_count": len(commits),
        "commits_sample": commits[:10],  # First 10 commits
        "local_path": str(local_path),
    }

    metadata_file = local_path / "backup_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(repo_metadata, f, indent=2, sort_keys=True)

    result = {
        "repo_name": repo_info["name"],
        "local_path": str(local_path),
        "is_fork": repo_info.get("is_fork", False),
        "is_private": repo_info.get("is_private", False),
        "commit_count": len(commits),
        # Return first 10 commits as sample
        "commits": commits[:10]
    }
    return result


@flow()
def backup_github_repositories(
    owner: str,
    until_date: datetime,
    credentials_block_name: str = "github-credentials",
):
    """
    Main flow to backup all GitHub repositories for a given owner.

    Args:
        owner: GitHub username or organization name
        until_date: Snapshot date for idempotent backups (all runs with same date produce identical results)
        credentials_block_name: Name of the Prefect GitHub credentials block

    Returns:
        List of repository backup results
    """
    import sys

    logger = get_run_logger()

    # Track workflow start time
    workflow_start = time.time()

    # Ensure until_date is timezone-aware
    if until_date.tzinfo is None:
        until_date = until_date.replace(tzinfo=timezone.utc)

    logger.info(f"Starting GitHub backup for {owner} (snapshot date: {until_date.isoformat()})")

    # Check if snapshot already exists (idempotency)
    if check_snapshot_exists(owner, until_date):
        logger.info(f"Snapshot already exists and is complete. Skipping backup.")
        # Optionally load and return existing manifest here
        return []

    # Load credentials from custom block and convert to GitHubCredentials
    github_block = GitHubBlock.load(credentials_block_name)
    github_credentials = GitHubCredentials(token=github_block.token)

    # Get all repositories for the owner (sorted for deterministic ordering)
    repositories = get_all_repositories(owner, github_credentials)

    logger.info(f"Found {len(repositories)} repositories for {owner}")

    # Process each repository - Prefect will automatically parallelize these tasks
    results = []
    failed_repos = []

    for repo_info in repositories:
        try:
            result = process_repository(
                repo_info=repo_info,
                github_credentials=github_credentials,
                until_date=until_date,
            )
            results.append(result)
        except Exception as e:
            # Log error and continue with other repos
            repo_name = repo_info.get("name", "unknown")
            logger.error(f"Failed to process repository {repo_name}: {str(e)}")

            # Save error information to backup directory
            error_info = {
                "repo_name": repo_name,
                "repo_url": repo_info.get("url", ""),
                "is_fork": repo_info.get("is_fork", False),
                "is_private": repo_info.get("is_private", False),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Determine category for error file path
            if repo_info.get("is_fork", False):
                category = "forks"
            elif repo_info.get("is_private", False):
                category = "private"
            else:
                category = "public"

            # Save error file in the repo's expected directory (with timestamp)
            snapshot_str = until_date.strftime("%Y-%m-%d")
            error_dir = (
                Path("./backups/local")
                / "github"
                / owner
                / "repositories"
                / snapshot_str
                / category
                / repo_name
            )
            error_dir.mkdir(parents=True, exist_ok=True)
            error_file = error_dir / "ERROR.json"

            with open(error_file, "w") as f:
                json.dump(error_info, f, indent=2)

            logger.warning(f"Error details saved to {error_file}")
            failed_repos.append(error_info)

    # Save backup manifest with enhanced metadata
    snapshot_str = until_date.strftime("%Y-%m-%d")
    manifest = {
        "backup_date": until_date.isoformat(),
        "snapshot_date_str": snapshot_str,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_version": "2.0.0",
        "python_version": sys.version,
        "owner": owner,
        "repository_count": len(results),
        "total_commits": sum(r.get("commit_count", 0) for r in results),
        "processing_duration_seconds": time.time() - workflow_start,
        "repositories": results,
        "failed_count": len(failed_repos),
        "failed_repositories": failed_repos,
    }

    # Update manifest path to include timestamp
    manifest_path = (
        Path("./backups/local")
        / "github"
        / owner
        / "repositories"
        / f"backup_manifest_{snapshot_str}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"Successfully backed up {len(results)} repositories")
    if failed_repos:
        logger.warning(f"Failed to backup {len(failed_repos)} repositories (see ERROR.json files for details)")
    logger.info(f"Manifest saved to {manifest_path}")

    return results


if __name__ == "__main__":
    backup_github_repositories(
        owner="freddiev4",
        until_date=datetime.now(timezone.utc),
    )
