import asyncio
import subprocess
import shutil
import time

from datetime import datetime, timezone, timedelta
from pathlib import Path

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from prefect_github import GitHubCredentials
from prefect_github.repository_owner import query_repository_owner_repositories
from prefect_github.repository import query_repository


@task(cache_policy=NO_CACHE)
def get_all_repositories(
    owner: str,
    github_credentials: GitHubCredentials
) -> list[dict]:
    """
    Get all repositories for a given owner with necessary fields for cloning.
    """
    # Query repositories - specify fields we want on each repository node
    # The library will automatically include nodes when we specify return_fields
    # Note: We don't include "owner" because it causes issues with nested repository queries
    # Note: query_repository_owner_repositories is async, so we use asyncio.run()
    # Add retry logic for transient API errors (like 502 Bad Gateway)
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
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
                    print(f"GitHub API returned 502 error, retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    print(f"GitHub API error after {max_retries} attempts: {error_msg}")
                    raise
            else:
                # Not a transient error, re-raise immediately
                raise
    
    # Extract repository information
    repo_list = []
    repos_data = repositories.get("nodes", [])

    print(f"Found {len(repo_list)} repositories for {owner}")
    print(f"Repositories: {[repo.get("name") for repo in repos_data]}")

    for repo in repos_data:
        repo_url = repo.get("url", "")
        # Ensure clone_url ends with .git
        clone_url = repo_url if repo_url.endswith(".git") else f"{repo_url}.git"
        
        # Default branch - we don't query it to avoid permission issues
        # Most repos use "main" or "master", default to "main"
        default_branch = "main"
        
        # Use the owner parameter we already have (since we're querying by owner)
        owner_login = owner
        
        repo_list.append({
            "name": repo.get("name"),
            "url": repo_url,
            "clone_url": clone_url,
            "is_private": repo.get("is_private", False),
            "default_branch": default_branch,
            "owner": owner_login
        })
    
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
        print(f"Error fetching commits for {owner}/{repo_name}: {e}")
        return []


@task(cache_policy=NO_CACHE)
def clone_repository_to_local(
    repo_info: dict,
    github_credentials: GitHubCredentials,
    local_backup_dir: Path = Path("./backups/local")
) -> Path:
    """Clone a repository to the local filesystem."""
    local_backup_dir.mkdir(parents=True, exist_ok=True)
    
    repo_path = local_backup_dir / repo_info["owner"] / repo_info["name"]
    
    # Remove existing directory if it exists
    if repo_path.exists():
        shutil.rmtree(repo_path)
    
    # Clone the repository
    clone_url = repo_info["clone_url"]
    
    # If private repo, use token in URL
    if repo_info["is_private"]:
        token = github_credentials.token.get_secret_value()
        # Format: https://token@github.com/owner/repo.git
        clone_url = clone_url.replace("https://", f"https://{token}@")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Successfully cloned {repo_info['name']} to {repo_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning {repo_info['name']}: {e.stderr}")
        raise
    
    return repo_path


@task()
def get_commits_from_local_repo(
    repo_path: Path,
    until_date: datetime = None
) -> list[dict]:
    """Get commits from a locally cloned repository using git log."""
    if until_date:
        # Ensure until_date is UTC-aware
        if until_date.tzinfo is None:
            until_date = until_date.replace(tzinfo=timezone.utc)
        elif until_date.tzinfo != timezone.utc:
            # Convert to UTC if it's in a different timezone
            until_date = until_date.astimezone(timezone.utc)
        
        # Format date for git log: --until="2024-01-01"
        date_str = until_date.strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", f"--until={date_str}", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso"],
            capture_output=True,
            text=True,
            check=True
        )
    else:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=iso"],
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
def process_repository(
    repo_info: dict,
    github_credentials: GitHubCredentials,
    until_date: datetime = None,
    local_backup_dir: Path = Path("./backups/local"),
) -> dict:
    """
    Process a single repository: clone, get commits, and backup.
    """
    # Clone to local filesystem
    local_path = clone_repository_to_local(
        repo_info=repo_info, 
        github_credentials=github_credentials, 
        local_backup_dir=local_backup_dir,
    )
    
    # Get commits up until the current date (or specified date)
    if until_date is None:
        until_date = datetime.now(timezone.utc)
    elif until_date.tzinfo is None:
        # If until_date is naive, assume it's UTC
        until_date = until_date.replace(tzinfo=timezone.utc)
    
    commits = get_commits_from_local_repo(
        local_path=local_path, 
        until_date=until_date,
    )
    
    repo_info = {
        "repo_name": repo_info["name"],
        "local_path": str(local_path),
        "commit_count": len(commits),
        # Return first 10 commits as sample
        "commits": commits[:10]
    }
    return repo_info


@flow()
def backup_github_repositories(
    owner: str,
    until_date: datetime,
):
    """
    Main flow to backup all GitHub repositories for a given owner.
    """
    # Load credentials once in the flow
    github_credentials = GitHubCredentials.load("github-freddiev4")
    
    # Get all repositories for the owner
    repositories = get_all_repositories(owner, github_credentials)
    
    print(f"Found {len(repositories)} repositories for {owner}")
    
    # Process each repository - Prefect will automatically parallelize these tasks
    results = []
    for repo_info in repositories:
        result = process_repository(
            repo_info=repo_info,
            github_credentials=github_credentials,
            until_date=until_date,
        )
        results.append(result)
    
    print(f"Successfully backed up {len(results)} repositories")
    return results


if __name__ == "__main__":
    backup_github_repositories(
        owner="freddiev4", 
        until_date=datetime.now(timezone.utc) - timedelta(days=1),
    )