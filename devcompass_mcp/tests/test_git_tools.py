import pytest
import os
import git
import shutil
from devcompass_mcp.tools.git_tools import (
    get_git_log,
    get_recent_changes,
    get_contributors,
    get_commit_diff
)

@pytest.fixture
def git_repo():
    # Setup temporary directory simulating repo root with a git repository
    root_dir = "/tmp/devcompass/test_git_repo"
    os.makedirs(root_dir, exist_ok=True)
    
    # Initialize git repo
    repo = git.Repo.init(root_dir)
    
    # Set config for test
    with repo.config_writer() as writer:
        writer.set_value("user", "name", "Test User")
        writer.set_value("user", "email", "test@user.com")
    
    # Create first commit
    file_path = os.path.join(root_dir, "file1.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Line 1\n")
        
    repo.index.add(["file1.txt"])
    author1 = git.Actor("Alice", "alice@test.com")
    commit1 = repo.index.commit("Initial commit", author=author1, committer=author1)
    
    # Create second commit
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("Line 2\n")
    repo.index.add(["file1.txt"])
    author2 = git.Actor("Bob", "bob@test.com")
    commit2 = repo.index.commit("Update file1", author=author2, committer=author2)
    
    yield root_dir, commit1, commit2
    
    shutil.rmtree(root_dir)

def test_get_git_log(git_repo):
    root_dir, c1, c2 = git_repo
    res = get_git_log(repo_path=root_dir)
    assert len(res["commits"]) == 2
    assert res["commits"][0]["hash"] == c2.hexsha
    assert "Bob" in res["commits"][0]["author"]
    assert res["commits"][1]["hash"] == c1.hexsha
    assert "Alice" in res["commits"][1]["author"]

def test_get_recent_changes(git_repo):
    root_dir, _, _ = git_repo
    res = get_recent_changes(repo_path=root_dir)
    assert len(res["changed_files"]) == 1
    assert res["changed_files"][0]["path"] == "file1.txt"
    assert res["changed_files"][0]["change_count"] == 2
    assert "Bob" in res["changed_files"][0]["last_changed_by"]

def test_get_contributors(git_repo):
    root_dir, _, _ = git_repo
    res = get_contributors(repo_path=root_dir)
    # Alice and Bob
    assert len(res["contributors"]) == 2
    names = {c["name"] for c in res["contributors"]}
    assert "Alice" in names
    assert "Bob" in names

def test_get_commit_diff(git_repo):
    root_dir, _, c2 = git_repo
    res = get_commit_diff(repo_path=root_dir, commit_hash=c2.hexsha)
    assert "file1.txt" in res["files_changed"]
    assert "+Line 2" in res["diff"]
