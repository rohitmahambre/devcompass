import os
import re
import pathlib
import time
import git
import shutil
import json
from ..security import validate_path, validate_url, is_blocked
from .file_tools import get_gitignore_spec, is_binary

def detect_stack(repo_path: str) -> dict:
    """
    Detect programming languages, frameworks, and build tools used in the repository by reading manifest files.
    """
    safe_path = validate_path(repo_path)
    root = pathlib.Path(safe_path)
    
    languages = []
    frameworks = []
    build_tools = []
    test_frameworks = []
    container = None
    ci_cd = []
    
    # 1. Check Python
    if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists() or (root / "setup.py").exists() or list(root.glob("*.py")):
        languages.append({"name": "Python", "confidence": "high", "detected_from": "requirements.txt/pyproject.toml/python files"})
        # Scan files for FastAPI, Flask, Django
        pyproject_path = root / "pyproject.toml"
        req_path = root / "requirements.txt"
        
        content = ""
        if pyproject_path.exists():
            try:
                content += pyproject_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        if req_path.exists():
            try:
                content += req_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
                
        if "fastapi" in content.lower():
            frameworks.append("FastAPI")
        if "flask" in content.lower():
            frameworks.append("Flask")
        if "django" in content.lower():
            frameworks.append("Django")
        if "sqlalchemy" in content.lower():
            frameworks.append("SQLAlchemy")
        if "pytest" in content.lower():
            test_frameworks.append("pytest")
            
    # 2. Check Node.js / JS / TS
    pkg_path = root / "package.json"
    if pkg_path.exists() or list(root.glob("*.js")) or list(root.glob("*.ts")):
        languages.append({"name": "JavaScript", "confidence": "high", "detected_from": "package.json/js files"})
        if list(root.glob("**/*.ts")) or list(root.glob("**/*.tsx")):
            languages.append({"name": "TypeScript", "confidence": "high", "detected_from": "ts/tsx files"})
            
        if pkg_path.exists():
            build_tools.append("npm")
            try:
                with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                    pkg_data = json.load(f)
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                
                if "react" in deps:
                    frameworks.append("React")
                if "vue" in deps:
                    frameworks.append("Vue")
                if "next" in deps:
                    frameworks.append("Next.js")
                if "express" in deps:
                    frameworks.append("Express")
                if "jest" in deps:
                    test_frameworks.append("Jest")
                if "mocha" in deps:
                    test_frameworks.append("Mocha")
                if "typescript" in deps:
                    build_tools.append("tsc")
            except Exception:
                pass
                
    # 3. Check Go
    go_mod = root / "go.mod"
    if go_mod.exists() or list(root.glob("*.go")):
        languages.append({"name": "Go", "confidence": "high", "detected_from": "go.mod/go files"})
        if go_mod.exists():
            build_tools.append("go build")
            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore")
                if "github.com/gin-gonic/gin" in content:
                    frameworks.append("Gin")
                if "github.com/labstack/echo" in content:
                    frameworks.append("Echo")
                if "github.com/gofiber/fiber" in content:
                    frameworks.append("Fiber")
            except Exception:
                pass
                
    # 4. Check Rust
    cargo_toml = root / "Cargo.toml"
    if cargo_toml.exists() or list(root.glob("*.rs")):
        languages.append({"name": "Rust", "confidence": "high", "detected_from": "Cargo.toml/rs files"})
        if cargo_toml.exists():
            build_tools.append("cargo")
            try:
                content = cargo_toml.read_text(encoding="utf-8", errors="ignore")
                if "tokio" in content:
                    frameworks.append("Tokio")
                if "actix-web" in content:
                    frameworks.append("Actix-web")
                if "axum" in content:
                    frameworks.append("Axum")
            except Exception:
                pass
                
    # 5. Check Java / Kotlin
    pom_xml = root / "pom.xml"
    build_gradle = root / "build.gradle"
    if pom_xml.exists() or build_gradle.exists() or list(root.glob("**/*.java")):
        languages.append({"name": "Java", "confidence": "high", "detected_from": "pom.xml/build.gradle/java files"})
        if list(root.glob("**/*.kt")):
            languages.append({"name": "Kotlin", "confidence": "high", "detected_from": "kt files"})
            
        content = ""
        if pom_xml.exists():
            build_tools.append("maven")
            try:
                content += pom_xml.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        if build_gradle.exists():
            build_tools.append("gradle")
            try:
                content += build_gradle.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
                
        if "spring-boot" in content.lower() or "springboot" in content.lower():
            frameworks.append("Spring Boot")
        if "quarkus" in content.lower():
            frameworks.append("Quarkus")
        if "junit" in content.lower():
            test_frameworks.append("JUnit")
            
    # 6. Check Container
    if (root / "Dockerfile").exists():
        container = "Docker"
    elif (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
        container = "Docker Compose"
        
    # 7. Check CI/CD
    github_workflows = root / ".github" / "workflows"
    if github_workflows.exists() and list(github_workflows.glob("*.yml")) or list(github_workflows.glob("*.yaml")):
        ci_cd.append("GitHub Actions")
    if list(root.glob("*.tf")):
        ci_cd.append("Terraform")
        
    return {
        "languages": languages,
        "frameworks": frameworks,
        "build_tools": build_tools,
        "test_frameworks": test_frameworks,
        "container": container,
        "ci_cd": ci_cd
    }

def find_entry_points(repo_path: str, detected_stack: dict = None) -> dict:
    """
    Identify likely entry point files — the files a developer would run to start the application.
    """
    safe_path = validate_path(repo_path)
    root = pathlib.Path(safe_path)
    
    if not detected_stack:
        detected_stack = detect_stack(repo_path)
        
    entry_points = []
    
    langs = {l["name"].lower() for l in detected_stack.get("languages", [])}
    
    # 1. Python Heuristics
    if "python" in langs:
        candidates = [
            ("main.py", "main", "high", "Standard main filename"),
            ("app.py", "server", "high", "Standard app/server filename"),
            ("manage.py", "cli", "high", "Django management entrypoint"),
            ("wsgi.py", "server", "medium", "WSGI application entrypoint"),
            ("asgi.py", "server", "medium", "ASGI application entrypoint"),
            ("cli.py", "cli", "medium", "Command line entrypoint"),
            ("run.py", "main", "medium", "Startup script"),
        ]
        for name, entry_type, conf, reason in candidates:
            p = root / name
            if p.exists():
                entry_points.append({
                    "path": str(p),
                    "type": entry_type,
                    "confidence": conf,
                    "reason": reason
                })
        # Check files containing if __name__ == "__main__"
        for py_file in root.rglob("*.py"):
            if len(entry_points) >= 10:
                break
            if py_file.name in [c[0] for c in candidates]:
                continue
            if is_blocked(str(py_file)):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if '__name__ == "__main__"' in content or "__name__ == '__main__'" in content:
                    entry_points.append({
                        "path": str(py_file),
                        "type": "main",
                        "confidence": "medium",
                        "reason": "Contains main execution block"
                    })
            except Exception:
                pass
                
    # 2. Node.js / JavaScript / TypeScript Heuristics
    if "javascript" in langs or "typescript" in langs:
        pkg_path = root / "package.json"
        if pkg_path.exists():
            try:
                with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                    pkg_data = json.load(f)
                main_file = pkg_data.get("main")
                if main_file:
                    main_p = root / main_file
                    if main_p.exists():
                        entry_points.append({
                            "path": str(main_p),
                            "type": "main",
                            "confidence": "high",
                            "reason": "Defined as 'main' in package.json"
                        })
            except Exception:
                pass
                
        candidates = [
            ("index.js", "main", "high", "Default Node.js entrypoint"),
            ("index.ts", "main", "high", "Default TypeScript entrypoint"),
            ("server.js", "server", "high", "Standard server startup"),
            ("server.ts", "server", "high", "Standard TypeScript server startup"),
            ("app.js", "server", "medium", "Standard application file"),
            ("app.ts", "server", "medium", "Standard TypeScript application file"),
        ]
        for name, entry_type, conf, reason in candidates:
            p = root / name
            if p.exists():
                # Avoid duplicate entry points
                if not any(ep["path"] == str(p) for ep in entry_points):
                    entry_points.append({
                        "path": str(p),
                        "type": entry_type,
                        "confidence": conf,
                        "reason": reason
                    })
                    
    # 3. Go Heuristics
    if "go" in langs:
        p = root / "main.go"
        if p.exists():
            entry_points.append({
                "path": str(p),
                "type": "main",
                "confidence": "high",
                "reason": "Standard Go entrypoint"
            })
            
    # 4. Rust Heuristics
    if "rust" in langs:
        p = root / "src" / "main.rs"
        if p.exists():
            entry_points.append({
                "path": str(p),
                "type": "main",
                "confidence": "high",
                "reason": "Standard Rust entrypoint"
            })
            
    # 5. Java / Kotlin Heuristics
    if "java" in langs or "kotlin" in langs:
        for java_file in root.rglob("*.java"):
            if len(entry_points) >= 10:
                break
            if is_blocked(str(java_file)):
                continue
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
                if "public static void main" in content:
                    entry_points.append({
                        "path": str(java_file),
                        "type": "main",
                        "confidence": "high",
                        "reason": "Contains Java public static void main method"
                    })
            except Exception:
                pass
                
    # 6. Generic Heuristics
    makefile = root / "Makefile"
    if makefile.exists():
        entry_points.append({
            "path": str(makefile),
            "type": "build_script",
            "confidence": "medium",
            "reason": "Makefile present for task execution"
        })
        
    return {"entry_points": entry_points}

def count_lines_of_code(repo_path: str, include_tests: bool = True) -> dict:
    """
    Count lines of code by language, excluding comments and blank lines where possible.
    """
    safe_path = validate_path(repo_path)
    root_path = pathlib.Path(safe_path)
    
    spec = get_gitignore_spec(safe_path)
    
    total_lines = 0
    total_files = 0
    by_language = {}
    
    # Supported extension mappings
    ext_map = {
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
        ".html": "HTML",
        ".css": "CSS",
    }
    
    # Iterate files
    for root, dirs, files in os.walk(root_path):
        # Prune hidden dirs and .git
        dirs[:] = [d for d in dirs if d != ".git" and not d.startswith(".")]
        
        # Optionally exclude tests
        if not include_tests:
            if "test" in root.lower() or "tests" in root.lower() or "__tests__" in root.lower():
                continue
                
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
                    
            ext = file_p.suffix.lower()
            lang = ext_map.get(ext)
            if not lang:
                continue
                
            if is_binary(str(file_p)):
                continue
                
            try:
                with open(file_p, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue
                
            # Parse lines
            file_lines = len(lines)
            blank = 0
            comment = 0
            
            # Simple line parsing based on language comments
            # Hash comments: Python, Ruby, Shell, YAML, TOML, Markdown (kind of)
            # Double-slash comments: JS, TS, Go, Rust, Java, Kotlin, C, C++
            is_hash_comment = ext in (".py", ".rb", ".sh", ".yml", ".yaml", ".toml")
            is_slash_comment = ext in (".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".cpp", ".cs")
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    blank += 1
                elif is_hash_comment and stripped.startswith("#"):
                    comment += 1
                elif is_slash_comment and (stripped.startswith("//") or stripped.startswith("/*") or stripped.endswith("*/")):
                    comment += 1
                    
            if lang not in by_language:
                by_language[lang] = {
                    "files": 0,
                    "lines": 0,
                    "blank": 0,
                    "comment": 0
                }
                
            by_language[lang]["files"] += 1
            by_language[lang]["lines"] += file_lines
            by_language[lang]["blank"] += blank
            by_language[lang]["comment"] += comment
            
            total_lines += file_lines
            total_files += 1
            
    return {
        "total_lines": total_lines,
        "total_files": total_files,
        "by_language": by_language
    }

def clone_repository(url: str, target_dir: str = "/tmp/devcompass") -> dict:
    """
    Clone a public GitHub repository to a local temporary directory.
    """
    if not validate_url(url):
        raise ValueError(f"Invalid GitHub URL format: {url}")
        
    repo_name = url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
        
    local_path = os.path.join(target_dir, repo_name)
    
    # Remove existing directory if it exists
    if os.path.exists(local_path):
        try:
            shutil.rmtree(local_path)
        except Exception as e:
            raise ValueError(f"Failed to clean target directory: {e}")
            
    os.makedirs(target_dir, exist_ok=True)
    
    start_time = time.time()
    try:
        # Shallow clone to limit download size
        repo = git.Repo.clone_from(url, local_path, depth=1)
        default_branch = repo.active_branch.name
    except Exception as e:
        raise ValueError(f"Failed to clone repository: {e}")
        
    clone_time = time.time() - start_time
    
    return {
        "local_path": local_path,
        "repo_name": repo_name,
        "default_branch": default_branch,
        "clone_time_seconds": round(clone_time, 2)
    }
