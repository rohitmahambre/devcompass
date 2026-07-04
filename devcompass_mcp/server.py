import sys
import os
from mcp.server.fastmcp import FastMCP

# Add parent directory to PYTHONPATH to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devcompass_mcp.tools.file_tools import (
    read_file,
    read_directory_tree,
    search_codebase,
    get_file_metadata
)
from devcompass_mcp.tools.git_tools import (
    get_git_log,
    get_recent_changes,
    get_contributors,
    get_commit_diff
)
from devcompass_mcp.tools.analysis_tools import (
    detect_stack,
    find_entry_points,
    count_lines_of_code,
    clone_repository
)

# FastMCP is used instead of the low-level MCP Server class because it handles
# stdio transport, tool registration, and JSON-RPC serialization automatically.
# Each agent spawns this server as a subprocess via StdioConnectionParams, so
# the server must be stateless — no shared memory between agent calls.
mcp = FastMCP("devcompass-mcp-server")

# Register File Tools
@mcp.tool(name="read_file")
def mcp_read_file(path: str, encoding: str = "utf-8", max_lines: int = 2000, start_line: int = 1) -> dict:
    """
    Read the content of a single file. Enforces safety and blocks credentials/secrets.
    """
    return read_file(path, encoding, max_lines, start_line)

@mcp.tool(name="read_directory_tree")
def mcp_read_directory_tree(path: str, max_depth: int = 6, include_hidden: bool = False, format: str = "ascii") -> dict:
    """
    Return a tree representation of a directory, respecting .gitignore.
    """
    return read_directory_tree(path, max_depth, include_hidden, format)

@mcp.tool(name="search_codebase")
def mcp_search_codebase(
    pattern: str, 
    path: str, 
    file_extensions: list[str] = None, 
    is_regex: bool = False, 
    case_sensitive: bool = True, 
    max_results: int = 50, 
    context_lines: int = 2
) -> dict:
    """
    Search for a pattern (literal string or regex) across files in the repository.
    """
    return search_codebase(pattern, path, file_extensions, is_regex, case_sensitive, max_results, context_lines)

@mcp.tool(name="get_file_metadata")
def mcp_get_file_metadata(path: str) -> dict:
    """
    Return metadata about a file without reading its full content.
    """
    return get_file_metadata(path)

# Register Git Tools
@mcp.tool(name="get_git_log")
def mcp_get_git_log(repo_path: str, max_commits: int = 20, author: str = None, since: str = None) -> dict:
    """
    Return recent commit history from the repository's git log.
    """
    return get_git_log(repo_path, max_commits, author, since)

@mcp.tool(name="get_recent_changes")
def mcp_get_recent_changes(repo_path: str, num_commits: int = 10) -> dict:
    """
    Return a summary of files changed in the last N commits.
    """
    return get_recent_changes(repo_path, num_commits)

@mcp.tool(name="get_contributors")
def mcp_get_contributors(repo_path: str, max_contributors: int = 20) -> dict:
    """
    Return contributor statistics from git history.
    """
    return get_contributors(repo_path, max_contributors)

@mcp.tool(name="get_commit_diff")
def mcp_get_commit_diff(repo_path: str, commit_hash: str, max_diff_lines: int = 500) -> dict:
    """
    Return the diff for a specific commit.
    """
    return get_commit_diff(repo_path, commit_hash, max_diff_lines)

# Register Analysis Tools
@mcp.tool(name="detect_stack")
def mcp_detect_stack(repo_path: str) -> dict:
    """
    Detect programming languages, frameworks, and build tools by reading manifest files.
    """
    return detect_stack(repo_path)

@mcp.tool(name="find_entry_points")
def mcp_find_entry_points(repo_path: str, detected_stack: dict = None) -> dict:
    """
    Identify likely entry point files (e.g. main.py, index.js, etc.).
    """
    return find_entry_points(repo_path, detected_stack)

@mcp.tool(name="count_lines_of_code")
def mcp_count_lines_of_code(repo_path: str, include_tests: bool = True) -> dict:
    """
    Count lines of code by language, excluding comments and blank lines.
    """
    return count_lines_of_code(repo_path, include_tests)

@mcp.tool(name="clone_repository")
def mcp_clone_repository(url: str, target_dir: str = "/tmp/devcompass") -> dict:
    """
    Clone a public GitHub repository to a local temporary directory.
    """
    return clone_repository(url, target_dir)

if __name__ == "__main__":
    # Start FastMCP server (will run over stdio by default)
    mcp.run()
