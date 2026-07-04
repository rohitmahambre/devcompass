import pathlib
import re

BLOCKED_EXACT_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    "credentials.json",
    "serviceAccountKey.json",
    "secrets.yaml",
    "secrets.yml",
    "id_rsa",
    "id_ed25519",
    ".netrc",
    ".npmrc",
})

BLOCKED_EXTENSIONS = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".crt",
    ".jks", ".keystore",
})

BLOCKED_PATTERNS = [
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*token.*\.(json|yml|yaml)$", re.IGNORECASE),
]

GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")

def validate_path(requested_path: str, repo_root: str = None) -> str:
    """
    Resolve symlinks and verify the canonical path is within repo_root (or allowed directories).
    Raises ValueError on traversal attempt.
    """
    requested_p = pathlib.Path(requested_path)
    
    if repo_root:
        if not requested_p.is_absolute():
            requested_p = pathlib.Path(repo_root) / requested_p
        canonical = requested_p.resolve()
        root = pathlib.Path(repo_root).resolve()
        try:
            canonical.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Path traversal attempt: {requested_path} resolves to {canonical}, "
                f"which is outside repo root {root}"
            )
        return str(canonical)
    else:
        canonical = requested_p.resolve()
        if not canonical.is_absolute():
            raise ValueError(f"Relative path without repo_root cannot be safely resolved: {requested_path}")
            
        allowed_roots = [
            pathlib.Path("/tmp/devcompass").resolve(),
            pathlib.Path("/tmp").resolve(),
            pathlib.Path("/code").resolve(),
        ]
        is_safe = False
        for root in allowed_roots:
            try:
                canonical.relative_to(root)
                is_safe = True
                break
            except ValueError:
                continue
        if not is_safe:
            raise ValueError(
                f"Path traversal attempt or unauthorized path: {requested_path} resolves to {canonical}, "
                f"which is not inside any allowed root directories"
            )
        return str(canonical)

def is_blocked(path: str) -> bool:
    """
    Check if a file path matches blocked patterns, exact names or extensions.
    """
    p = pathlib.Path(path)
    name = p.name
    
    if name in BLOCKED_EXACT_NAMES:
        return True
        
    # Check extensions
    ext = p.suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        return True
        
    # Check regex patterns against name
    for pattern in BLOCKED_PATTERNS:
        if pattern.match(name):
            return True
            
    # Also prevent accessing .git directory files (except we do want to prevent config access)
    if ".git" in p.parts:
        # Allow checking git history/logs but block config and other git internals
        if name in ("config", "description", "credentials"):
            return True
            
    return False

def validate_url(url: str) -> bool:
    """
    Validate repository URL matches expected GitHub pattern.
    """
    return bool(GITHUB_URL_PATTERN.match(url))
