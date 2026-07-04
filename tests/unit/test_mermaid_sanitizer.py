import pytest
from app.agents.orchestrator import sanitize_mermaid

def test_sanitize_mermaid_basic():
    diagram = "graph TD\n    User[User/Client] --> Server[Gunicorn / uWSGI]"
    expected = 'graph TD\n    User["User/Client"] --> Server["Gunicorn / uWSGI"]'
    assert sanitize_mermaid(diagram) == expected

def test_sanitize_mermaid_parentheses():
    diagram = "graph TD\n    Node2([Some (Parenthesis) Node]) --> Node3{Brace node}"
    expected = 'graph TD\n    Node2(["Some (Parenthesis) Node"]) --> Node3{"Brace node"}'
    assert sanitize_mermaid(diagram) == expected

def test_sanitize_mermaid_already_quoted():
    diagram = 'graph TD\n    Node4["Already quoted"] --> Node5(["Also \\"quoted\\" node"])'
    sanitized = sanitize_mermaid(diagram)
    assert 'Node4["Already quoted"]' in sanitized
    assert 'Node5(["Also \\"quoted\\" node"])' in sanitized

def test_sanitize_mermaid_comments():
    # Since comments are not preceded by node start rules (like start of line or space or connection), they should not match
    # Wait, the comment line starts with %%, so it won't match our node prefix.
    diagram = '%% this is a comment with brackets [test]\n    App[Flask App Object]'
    expected = '%% this is a comment with brackets [test]\n    App["Flask App Object"]'
    assert sanitize_mermaid(diagram) == expected
