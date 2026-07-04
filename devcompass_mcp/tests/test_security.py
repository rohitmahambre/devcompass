import pytest
import os
import pathlib
from devcompass_mcp.security import validate_path, is_blocked, validate_url

def test_validate_path_allowed():
    # Test valid path inside allowed root (workspace)
    workspace = "/Users/rmahambre/agentdev/capstore"
    valid_file = os.path.join(workspace, "devcompass-spec.md")
    resolved = validate_path(valid_file, workspace)
    assert resolved == os.path.abspath(valid_file)

def test_validate_path_traversal():
    workspace = "/Users/rmahambre/agentdev/capstore"
    invalid_file = os.path.join(workspace, "../../../etc/passwd")
    with pytest.raises(ValueError, match="Path traversal attempt"):
        validate_path(invalid_file, workspace)

def test_is_blocked_exact_names():
    assert is_blocked(".env") is True
    assert is_blocked(".env.local") is True
    assert is_blocked("credentials.json") is True
    assert is_blocked("secrets.yaml") is True
    assert is_blocked("main.py") is False

def test_is_blocked_extensions():
    assert is_blocked("key.pem") is True
    assert is_blocked("id_rsa.key") is True
    assert is_blocked("cert.crt") is True
    assert is_blocked("index.html") is False

def test_is_blocked_patterns():
    assert is_blocked("my_secret_token.json") is True
    assert is_blocked("passwords.txt") is True
    assert is_blocked("user_credentials.yaml") is True

def test_validate_url():
    assert validate_url("https://github.com/pallets/flask") is True
    assert validate_url("https://github.com/django/django") is True
    assert validate_url("https://github.com/django/django.git") is True
    assert validate_url("http://github.com/pallets/flask") is False
    assert validate_url("https://gitlab.com/pallets/flask") is False
