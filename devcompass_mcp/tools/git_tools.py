import re
import pathlib
import git
from ..security import validate_path

COMMIT_HASH_PATTERN = re.compile(r"^[a-f0-9]{4,40}$")

def get_git_repo(repo_path: str) -> git.Repo:
    """Helper to validate path and open git Repo."""
    safe_path = validate_path(repo_path)
    try:
        # Check if the path actually contains a git repo
        repo = git.Repo(safe_path, search_parent_directories=True)
        return repo
    except git.exc.InvalidGitRepositoryError:
        raise ValueError(f"Not a valid Git repository: {repo_path}")
    except Exception as e:
        raise ValueError(f"Failed to access Git repository: {e}")

def get_git_log(repo_path: str, max_commits: int = 20, author: str = None, since: str = None) -> dict:
    """
    Return recent commit history from the repository's git log.
    """
    repo = get_git_repo(repo_path)
    kwargs = {
        "max_count": max_commits
    }
    
    if author:
        kwargs["author"] = author
    if since:
        kwargs["since"] = since
        
    try:
        commits = list(repo.iter_commits(**kwargs))
    except Exception as e:
        raise ValueError(f"Failed to retrieve git log: {e}")
        
    commit_list = []
    for commit in commits:
        # Count files changed in this commit
        # For the first commit, there is no parent, so diff against NULL_TREE
        try:
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit)
            else:
                diffs = commit.diff(git.NULL_TREE)
            files_changed = len(diffs)
        except Exception:
            files_changed = 0
            
        commit_list.append({
            "hash": commit.hexsha,
            "short_hash": commit.hexsha[:7],
            "author": f"{commit.author.name} <{commit.author.email}>",
            "date": commit.authored_datetime.isoformat(),
            "message": commit.message.strip(),
            "files_changed": files_changed
        })
        
    return {"commits": commit_list}

def get_recent_changes(repo_path: str, num_commits: int = 10) -> dict:
    """
    Return a summary of files changed in the last N commits.
    """
    repo = get_git_repo(repo_path)
    
    try:
        commits = list(repo.iter_commits(max_count=num_commits))
    except Exception as e:
        raise ValueError(f"Failed to retrieve commits: {e}")
        
    file_changes = {}
    
    for commit in commits:
        try:
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit)
            else:
                diffs = commit.diff(git.NULL_TREE)
                
            for diff in diffs:
                # Get the path of the file
                path = diff.b_path or diff.a_path
                if not path:
                    continue
                    
                if path not in file_changes:
                    file_changes[path] = {
                        "path": path,
                        "change_count": 0,
                        "last_changed_by": f"{commit.author.name} <{commit.author.email}>",
                        "last_changed_at": commit.authored_datetime.isoformat()
                    }
                file_changes[path]["change_count"] += 1
        except Exception:
            continue
            
    # Sort by change count descending
    sorted_changes = sorted(file_changes.values(), key=lambda x: x["change_count"], reverse=True)
    return {"changed_files": sorted_changes}

def get_contributors(repo_path: str, max_contributors: int = 20) -> dict:
    """
    Return contributor statistics from git history.
    """
    repo = get_git_repo(repo_path)
    
    try:
        commits = list(repo.iter_commits())
    except Exception as e:
        raise ValueError(f"Failed to retrieve commits: {e}")
        
    stats = {}
    for commit in commits:
        author_key = (commit.author.name or "Unknown", commit.author.email or "unknown@email.com")
        
        if author_key not in stats:
            stats[author_key] = {
                "name": author_key[0],
                "email": author_key[1],
                "commit_count": 0,
                "first_commit": commit.authored_datetime.isoformat(),
                "last_commit": commit.authored_datetime.isoformat(),
                "_first_dt": commit.authored_datetime,
                "_last_dt": commit.authored_datetime
            }
            
        stats[author_key]["commit_count"] += 1
        
        # Track first and last commit datetimes
        if commit.authored_datetime < stats[author_key]["_first_dt"]:
            stats[author_key]["_first_dt"] = commit.authored_datetime
            stats[author_key]["first_commit"] = commit.authored_datetime.isoformat()
            
        if commit.authored_datetime > stats[author_key]["_last_dt"]:
            stats[author_key]["_last_dt"] = commit.authored_datetime
            stats[author_key]["last_commit"] = commit.authored_datetime.isoformat()
            
    # Remove internal datetime objects
    for stat in stats.values():
        del stat["_first_dt"]
        del stat["_last_dt"]
        
    # Sort by commit count descending
    sorted_contributors = sorted(stats.values(), key=lambda x: x["commit_count"], reverse=True)
    return {"contributors": sorted_contributors[:max_contributors]}

def get_commit_diff(repo_path: str, commit_hash: str, max_diff_lines: int = 500) -> dict:
    """
    Return the diff for a specific commit.
    """
    repo = get_git_repo(repo_path)
    
    if not COMMIT_HASH_PATTERN.match(commit_hash):
        raise ValueError(f"Invalid commit hash: {commit_hash}")
        
    try:
        commit = repo.commit(commit_hash)
    except Exception:
        raise ValueError(f"Commit not found: {commit_hash}")
        
    try:
        # Run diff
        # Get diff text
        if commit.parents:
            parent = commit.parents[0]
            diff_text = repo.git.diff(parent.hexsha, commit.hexsha)
            diffs = parent.diff(commit)
        else:
            diff_text = repo.git.show(commit.hexsha, format="")
            diffs = commit.diff(git.NULL_TREE)
            
        files_changed = list({d.b_path or d.a_path for d in diffs if d.b_path or d.a_path})
    except Exception as e:
        raise ValueError(f"Failed to generate diff: {e}")
        
    lines = diff_text.splitlines()
    total_lines = len(lines)
    truncated = total_lines > max_diff_lines
    
    result_diff = "\n".join(lines[:max_diff_lines])
    
    return {
        "diff": result_diff,
        "files_changed": files_changed,
        "truncated": truncated
    }
