import pytest
import os
import tempfile
import pathlib
from devcompass_mcp.tools.file_tools import (
    read_file,
    read_directory_tree,
    search_codebase,
    get_file_metadata
)

@pytest.fixture
def temp_workspace():
    # Setup temporary directory simulating repo root
    # Note: We must make sure it is resolved and matches allowed roots
    # To run test safely, we will create it inside /tmp/devcompass/test_workspace
    root_dir = "/tmp/devcompass/test_workspace"
    os.makedirs(root_dir, exist_ok=True)
    
    # Create some mock files
    with open(os.path.join(root_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Test Project\nThis is a test readme.\nLine 3 of readme.\n")
        
    with open(os.path.join(root_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n")
        
    # Create blocked file
    with open(os.path.join(root_dir, ".env"), "w", encoding="utf-8") as f:
        f.write("SECRET_KEY=123456\n")
        
    # Create a subfolder
    sub_dir = os.path.join(root_dir, "app")
    os.makedirs(sub_dir, exist_ok=True)
    with open(os.path.join(sub_dir, "helper.py"), "w", encoding="utf-8") as f:
        f.write("def helper():\n    pass\n")
        
    yield root_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(root_dir)

def test_read_file_success(temp_workspace):
    path = os.path.join(temp_workspace, "README.md")
    res = read_file(path=path)
    assert "Test Project" in res["content"]
    assert res["total_lines"] == 3
    assert res["truncated"] is False

def test_read_file_line_range(temp_workspace):
    path = os.path.join(temp_workspace, "main.py")
    res = read_file(path=path, start_line=2, max_lines=2)
    assert "print('Hello World')" in res["content"]
    assert "if __name__" not in res["content"]
    assert res["total_lines"] == 5
    assert res["truncated"] is True

def test_read_file_blocked(temp_workspace):
    path = os.path.join(temp_workspace, ".env")
    with pytest.raises(ValueError, match="Permission denied"):
        read_file(path=path)

def test_read_directory_tree(temp_workspace):
    res = read_directory_tree(path=temp_workspace)
    tree_str = res["tree"]
    assert "README.md" in tree_str
    assert "main.py" in tree_str
    assert "app/" in tree_str
    assert "helper.py" in tree_str
    assert ".env" not in tree_str # Blocked/ignored by default

def test_search_codebase(temp_workspace):
    res = search_codebase(pattern="Hello World", path=temp_workspace)
    assert len(res["matches"]) == 1
    assert res["matches"][0]["line"] == 2
    assert "main.py" in res["matches"][0]["file"]

def test_get_file_metadata(temp_workspace):
    path = os.path.join(temp_workspace, "main.py")
    res = get_file_metadata(path=path)
    assert res["language"] == "Python"
    assert res["line_count"] == 5
    assert res["is_binary"] is False
