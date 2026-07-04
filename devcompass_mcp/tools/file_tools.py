import os
import pathlib
import re
import pathspec
from ..security import validate_path, is_blocked

def is_binary(file_path: str) -> bool:
    """Check if a file is binary by searching for a null byte in the first 512 bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(512)
            return b"\x00" in chunk
    except Exception:
        return False

def get_gitignore_spec(directory: str):
    """Parse .gitignore files from the directory up to allowed roots."""
    patterns = []
    p = pathlib.Path(directory).resolve()
    
    # We ascend up the directory tree to find .gitignore patterns
    # Stop ascending if we are no longer in an allowed root
    allowed_roots = [
        pathlib.Path("/tmp/devcompass").resolve(),
        pathlib.Path("/tmp").resolve(),
        pathlib.Path("/code").resolve(),
    ]
    
    while p.exists():
        is_in_allowed_root = any(p == root or root in p.parents for root in allowed_roots)
        if not is_in_allowed_root:
            break
            
        gitignore_path = p / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    patterns.extend(f.readlines())
            except Exception:
                pass
                
        if p == p.parent:
            break
        p = p.parent
        
    if patterns:
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return None

def read_file(path: str, encoding: str = "utf-8", max_lines: int = 2000, start_line: int = 1) -> dict:
    """
    Read the content of a single file within path safety constraints.
    """
    safe_path = validate_path(path)
    if is_blocked(safe_path):
        raise ValueError(f"Permission denied: File is blocked by security policy: {path}")
        
    if is_binary(safe_path):
        raise ValueError(f"Cannot read binary file: {path}")
        
    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"File not found: {path}")
        
    # Check file size (500 KB limit)
    size_kb = os.path.getsize(safe_path) / 1024
    if size_kb > 500:
        raise ValueError(f"File exceeds maximum size of 500 KB: {size_kb:.1f} KB")

    try:
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        # Fallback to latin-1
        if encoding != "latin-1":
            try:
                with open(safe_path, "r", encoding="latin-1", errors="replace") as f:
                    lines = f.readlines()
            except Exception as e2:
                raise ValueError(f"Failed to read file: {e2}")
        else:
            raise ValueError(f"Failed to read file: {e}")

    total_lines = len(lines)
    
    # 1-indexed lines slice
    start_idx = max(0, start_line - 1)
    end_idx = start_idx + max_lines
    
    selected_lines = lines[start_idx:end_idx]
    content = "".join(selected_lines)
    truncated = end_idx < total_lines

    if len(content) > 8000:
        content = content[:8000] + "\n... [TRUNCATED TO PREVENT PAYLOAD OVERFLOW]"
        truncated = True

    return {
        "content": content,
        "total_lines": total_lines,
        "truncated": truncated,
        "path": safe_path
    }

def read_directory_tree(path: str, max_depth: int = 6, include_hidden: bool = False, format: str = "ascii") -> dict:
    """
    Return a tree representation of a directory, respecting .gitignore and blocked files.
    """
    safe_path = validate_path(path)
    if is_blocked(safe_path):
        raise ValueError(f"Permission denied: Path is blocked: {path}")
        
    root_path = pathlib.Path(safe_path)
    if not root_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
        
    spec = get_gitignore_spec(safe_path)
    
    total_files = 0
    total_dirs = 0
    file_limit = 50000
    
    def build_tree_ascii(dir_path, current_depth=0, prefix=""):
        nonlocal total_files, total_dirs
        if current_depth > max_depth or (total_files + total_dirs) >= file_limit:
            return ""
            
        try:
            entries = sorted(list(dir_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return f"{prefix}Permission Denied\n"
            
        lines = []
        filtered_entries = []
        
        for entry in entries:
            # Skip hidden files unless include_hidden is True
            if not include_hidden and entry.name.startswith(".") and entry.name != ".gitignore":
                continue
            if entry.name == ".git":
                continue
            if is_blocked(str(entry)):
                continue
                
            # Check gitignore
            if spec:
                # Get relative path from safe_path (the root of the search)
                try:
                    rel_str = str(entry.relative_to(root_path))
                    if entry.is_dir():
                        rel_str += "/"
                    if spec.match_file(rel_str):
                        continue
                except ValueError:
                    pass
            filtered_entries.append(entry)
            
        for i, entry in enumerate(filtered_entries):
            if (total_files + total_dirs) >= file_limit:
                lines.append(f"{prefix}└── [Truncated: reached file limit]")
                break
                
            is_last = (i == len(filtered_entries) - 1)
            connector = "└── " if is_last else "├── "
            
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                total_dirs += 1
                next_prefix = prefix + ("    " if is_last else "│   ")
                subtree = build_tree_ascii(entry, current_depth + 1, next_prefix)
                if subtree:
                    lines.append(subtree.rstrip("\n"))
            else:
                lines.append(f"{prefix}{connector}{entry.name}")
                total_files += 1
                
        return "\n".join(lines) + "\n"

    def build_tree_json(dir_path, current_depth=0):
        nonlocal total_files, total_dirs
        if current_depth > max_depth or (total_files + total_dirs) >= file_limit:
            return {"name": dir_path.name, "type": "directory", "children": [], "truncated": True}
            
        node = {
            "name": dir_path.name,
            "type": "directory",
            "children": []
        }
        
        try:
            entries = sorted(list(dir_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            node["error"] = "Permission Denied"
            return node
            
        for entry in entries:
            if (total_files + total_dirs) >= file_limit:
                node["truncated"] = True
                break
                
            if not include_hidden and entry.name.startswith(".") and entry.name != ".gitignore":
                continue
            if entry.name == ".git":
                continue
            if is_blocked(str(entry)):
                continue
                
            if spec:
                try:
                    rel_str = str(entry.relative_to(root_path))
                    if entry.is_dir():
                        rel_str += "/"
                    if spec.match_file(rel_str):
                        continue
                except ValueError:
                    pass
                    
            if entry.is_dir():
                total_dirs += 1
                node["children"].append(build_tree_json(entry, current_depth + 1))
            else:
                total_files += 1
                node["children"].append({
                    "name": entry.name,
                    "type": "file",
                    "size_bytes": entry.stat().st_size
                })
                
        return node

    if format == "json":
        tree_data = build_tree_json(root_path)
        return {
            "tree": tree_data,
            "total_files": total_files,
            "total_dirs": total_dirs,
            "gitignore_applied": spec is not None
        }
    else:
        tree_str = f"{root_path.name}/\n" + build_tree_ascii(root_path)
        return {
            "tree": tree_str,
            "total_files": total_files,
            "total_dirs": total_dirs,
            "gitignore_applied": spec is not None
        }

def search_codebase(
    pattern: str, 
    path: str, 
    file_extensions: list[str] = None, 
    is_regex: bool = False, 
    case_sensitive: bool = True, 
    max_results: int = 50, 
    context_lines: int = 2
) -> dict:
    """
    Search for a pattern across files in the repository.
    """
    safe_path = validate_path(path)
    if is_blocked(safe_path):
        raise ValueError(f"Permission denied: Path is blocked: {path}")
        
    root_path = pathlib.Path(safe_path)
    if not root_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
        
    # ReDoS Protection
    # Rejects regex pattern if alternations are extremely long or complex
    if is_regex and len(pattern) > 500:
        raise ValueError("Regex pattern too complex (exceeds length limits)")
        
    if is_regex:
        # Check alternations
        alternation_count = len(re.findall(r'\|', pattern))
        if alternation_count > 20:
            raise ValueError("Regex pattern contains too many alternations (ReDoS protection)")
            
    # Compile regex pattern
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        if is_regex:
            regex = re.compile(pattern, flags)
        else:
            # Escape literal search
            regex = re.compile(re.escape(pattern), flags)
    except re.error as e:
        raise ValueError(f"Invalid regular expression: {e}")
        
    spec = get_gitignore_spec(safe_path)
    matches = []
    total_matches = 0
    truncated = False
    
    # Traverse files
    # Use rglob or walk
    paths_to_search = []
    if root_path.is_file():
        paths_to_search = [root_path]
    else:
        for root, dirs, files in os.walk(root_path):
            # Prune .git and hidden dirs
            dirs[:] = [d for d in dirs if d != ".git" and (include_hidden or not d.startswith("."))]
            
            for file in files:
                file_p = pathlib.Path(root) / file
                if is_blocked(str(file_p)):
                    continue
                if spec:
                    try:
                        rel_str = str(file_p.relative_to(root_path))
                        if spec.match_file(rel_str):
                            continue
                    except ValueError:
                        pass
                # Check extensions
                if file_extensions:
                    if file_p.suffix not in file_extensions:
                        continue
                paths_to_search.append(file_p)
                
    for file_p in paths_to_search:
        if len(matches) >= max_results:
            truncated = True
            break
            
        if is_binary(str(file_p)):
            continue
            
        try:
            with open(file_p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            continue
            
        for line_idx, line in enumerate(lines):
            if regex.search(line):
                total_matches += 1
                if len(matches) < max_results:
                    # Collect context lines
                    start_ctx = max(0, line_idx - context_lines)
                    end_ctx = min(len(lines), line_idx + context_lines + 1)
                    
                    context_before = "".join(lines[start_ctx:line_idx])
                    context_after = "".join(lines[line_idx+1:end_ctx])
                    
                    matches.append({
                        "file": str(file_p),
                        "line": line_idx + 1,
                        "match": line.strip(),
                        "context_before": context_before,
                        "context_after": context_after
                    })
                    
    return {
        "matches": matches,
        "total_matches": total_matches,
        "truncated": truncated
    }

def get_file_metadata(path: str) -> dict:
    """
    Return metadata about a file without reading its full content.
    """
    safe_path = validate_path(path)
    if is_blocked(safe_path):
        raise ValueError(f"Permission denied: Path is blocked: {path}")
        
    p = pathlib.Path(safe_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {path}")
        
    stat = p.stat()
    is_bin = is_binary(safe_path)
    
    # Estimate line count
    line_count = 0
    if not is_bin:
        try:
            with open(safe_path, "rb") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            pass
            
    # Detect language by extension
    ext_to_lang = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "React (JS)",
        ".tsx": "React (TS)",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".kt": "Kotlin",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C Header",
        ".cs": "C#",
        ".rb": "Ruby",
        ".php": "PHP",
        ".sh": "Shell Script",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".json": "JSON",
        ".toml": "TOML",
        ".md": "Markdown",
        ".txt": "Text",
        ".html": "HTML",
        ".css": "CSS",
    }
    language = ext_to_lang.get(p.suffix.lower(), "Unknown")
    
    return {
        "path": safe_path,
        "size_bytes": stat.st_size,
        "last_modified": datetime_str(stat.st_mtime),
        "language": language,
        "line_count": line_count,
        "is_binary": is_bin
    }

def datetime_str(timestamp: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
