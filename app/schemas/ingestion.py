from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class RepoIngestionInput(BaseModel):
    repo_url: Optional[str] = Field(
        None,
        description="GitHub URL to clone, e.g. https://github.com/owner/repo"
    )
    local_path: Optional[str] = Field(
        None,
        description="Absolute path to a local repository directory"
    )
    max_file_size_kb: int = Field(
        100,
        description="Skip files larger than this size in kilobytes"
    )

class RepoIngestionOutput(BaseModel):
    repo_path: str = Field(description="Absolute path to the ingested repository on disk")
    file_tree: str = Field(description="ASCII tree of the repository file structure")
    detected_stack: dict = Field(description="Detected languages, frameworks, and build tools")
    entry_points: List[str] = Field(description="Identified entry point files (main.py, index.js, etc.)")
    dependency_summary: str = Field(description="Summary of dependencies from manifest files")
    key_file_paths: List[str] = Field(description="Paths to critical files: README, config, entrypoints (content to be read on demand)")
    total_files: int = Field(description="Total count of files in repo")
    total_lines: int = Field(description="Total lines of code in repo")
