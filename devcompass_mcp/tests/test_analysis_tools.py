import pytest
import os
import shutil
from devcompass_mcp.tools.analysis_tools import (
    detect_stack,
    find_entry_points,
    count_lines_of_code,
    clone_repository
)

@pytest.fixture
def sample_project():
    root_dir = "/tmp/devcompass/test_analysis_repo"
    os.makedirs(root_dir, exist_ok=True)
    
    # Create pyproject.toml
    with open(os.path.join(root_dir, "pyproject.toml"), "w", encoding="utf-8") as f:
        f.write("[project]\nname = 'test'\ndependencies = ['fastapi', 'sqlalchemy']\n")
        
    # Create app.py
    with open(os.path.join(root_dir, "app.py"), "w", encoding="utf-8") as f:
        f.write("# This is a main application\n\n\ndef start():\n    pass\n\nif __name__ == '__main__':\n    start()\n")
        
    # Create helper.py
    with open(os.path.join(root_dir, "helper.py"), "w", encoding="utf-8") as f:
        f.write("def help():\n    pass\n")
        
    # Create Dockerfile
    with open(os.path.join(root_dir, "Dockerfile"), "w", encoding="utf-8") as f:
        f.write("FROM python:3.11\nCOPY . /app\n")
        
    yield root_dir
    
    shutil.rmtree(root_dir)

def test_detect_stack(sample_project):
    res = detect_stack(repo_path=sample_project)
    langs = [l["name"] for l in res["languages"]]
    assert "Python" in langs
    assert "FastAPI" in res["frameworks"]
    assert res["container"] == "Docker"

def test_find_entry_points(sample_project):
    res = find_entry_points(repo_path=sample_project)
    paths = [os.path.basename(ep["path"]) for ep in res["entry_points"]]
    assert "app.py" in paths

def test_count_lines_of_code(sample_project):
    res = count_lines_of_code(repo_path=sample_project)
    assert res["total_files"] == 3  # pyproject.toml, app.py, helper.py (Dockerfile skipped as not in ext_map)
    assert "Python" in res["by_language"]
    assert res["by_language"]["Python"]["files"] == 2
    # pyproject.toml (3 lines) + app.py (8 lines) + helper.py (2 lines) = 13 lines
    assert res["total_lines"] == 13

def test_clone_repository():
    # Test with invalid URL
    with pytest.raises(ValueError, match="Invalid GitHub URL format"):
        clone_repository("https://notgithub.com/owner/repo")
