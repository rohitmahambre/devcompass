"""
Tests for Mermaid diagram sanitization and HTML rendering pipeline.

Covers:
  - sanitize_mermaid: keyword skipping, quote preservation, node label quoting
  - mermaid_to_html: base64 round-trip, no html.escape corruption, no inline scripts
"""

import base64
import pytest

# ── imports ────────────────────────────────────────────────────────────────────
from app.agents.orchestrator import sanitize_mermaid
from ui.gradio_app import mermaid_to_html


# ══════════════════════════════════════════════════════════════════════════════
# sanitize_mermaid
# ══════════════════════════════════════════════════════════════════════════════

FLASK_DIAGRAM = """graph TD
    subgraph External
        User[User/Client]
    end
    subgraph "Web Server (WSGI)"
        Server[Gunicorn / uWSGI]
    end
    subgraph "Core Dependencies"
        Werkzeug[Werkzeug: Routing & WSGI]
        Jinja2[Jinja2: Templating]
        Click[Click: CLI]
    end
    User --> Server
    App -- Manages --> Routing"""

COMPLEX_DIAGRAM = """graph TD
    subgraph "Browser/Client"
        A["User Request (HTTP)"]
    end
    subgraph "WSGI Server (e.g., Gunicorn, uWSGI)"
        B["WSGI Server"]
    end
    A --> B
    B --> C
    G -.-> E"""


class TestSanitizeMermaid:

    def test_strips_fences(self):
        fenced = "```mermaid\ngraph TD\n    A --> B\n```"
        result = sanitize_mermaid(fenced)
        assert not result.startswith("```")
        assert "graph TD" in result

    def test_subgraph_quoted_label_preserved(self):
        """subgraph "Web Server (WSGI)" must NOT be corrupted."""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert 'subgraph "Web Server (WSGI)"' in result, (
            f"Subgraph label was corrupted.\nGot:\n{result}"
        )

    def test_subgraph_quotes_not_nested(self):
        """Must not produce subgraph "Web Server("WSGI")" style corruption."""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert 'Server("WSGI")' not in result, (
            f"Sanitizer corrupted the subgraph label.\nGot:\n{result}"
        )

    def test_node_labels_with_slash_quoted(self):
        """User[User/Client] → User["User/Client"]"""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert 'User["User/Client"]' in result

    def test_node_labels_with_colon_quoted(self):
        """Jinja2[Jinja2: Templating] → Jinja2["Jinja2: Templating"]"""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert 'Jinja2["Jinja2: Templating"]' in result

    def test_node_labels_with_ampersand_quoted(self):
        """Werkzeug[Werkzeug: Routing & WSGI] → quoted"""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert 'Werkzeug["Werkzeug: Routing & WSGI"]' in result

    def test_already_quoted_nodes_not_double_quoted(self):
        """Nodes already wrapped in double quotes must not be re-quoted."""
        diagram = 'graph TD\n    A["Already quoted label"]'
        result = sanitize_mermaid(diagram)
        # Should have exactly one set of quotes, not '["\"Already...\""]'
        assert result.count('"Already') == 1

    def test_already_quoted_subgraph_not_changed(self):
        result = sanitize_mermaid(COMPLEX_DIAGRAM)
        assert 'subgraph "Browser/Client"' in result
        assert 'subgraph "WSGI Server (e.g., Gunicorn, uWSGI)"' in result

    def test_edge_labels_not_corrupted(self):
        """App -- Manages --> Routing must not have its edge label quoted."""
        result = sanitize_mermaid(FLASK_DIAGRAM)
        assert "-- Manages -->" in result

    def test_empty_string(self):
        assert sanitize_mermaid("") == ""

    def test_graph_keyword_line_not_modified(self):
        diagram = "graph TD\n    A --> B"
        result = sanitize_mermaid(diagram)
        assert result.startswith("graph TD")


# ══════════════════════════════════════════════════════════════════════════════
# mermaid_to_html
# ══════════════════════════════════════════════════════════════════════════════

class TestMermaidToHtml:

    def test_empty_returns_placeholder(self):
        out = mermaid_to_html("")
        assert "Diagram will render here" in out

    def test_none_falsy_returns_placeholder(self):
        out = mermaid_to_html(None)
        assert "Diagram will render here" in out

    def test_contains_mermaid_class(self):
        out = mermaid_to_html("graph TD\n    A --> B")
        assert 'class="mermaid"' in out

    def test_uses_data_src_not_inline_content(self):
        """Content must be base64 in data-src, NOT raw text in the div."""
        diagram = "graph TD\n    A --> B"
        out = mermaid_to_html(diagram)
        assert "data-src=" in out
        # Raw arrows should not appear directly (they're base64 encoded)
        assert "A --> B" not in out

    def test_no_inline_script_tag(self):
        """No <script> in the HTML output — Gradio blocks inline scripts."""
        out = mermaid_to_html("graph TD\n    A --> B")
        assert "<script" not in out.lower()

    def test_base64_decodes_to_original(self):
        """The data-src value must decode back to the original diagram text."""
        diagram = "graph TD\n    A --> B\n    B --> C"
        out = mermaid_to_html(diagram)
        # Extract the base64 value from data-src="..."
        import re
        m = re.search(r'data-src="([^"]+)"', out)
        assert m, "No data-src attribute found in output"
        decoded = base64.b64decode(m.group(1)).decode("utf-8")
        assert decoded == diagram

    def test_no_html_escape_corruption_arrows(self):
        """'--> ' must not become '--&gt;' in the output."""
        diagram = "graph TD\n    A --> B"
        out = mermaid_to_html(diagram)
        assert "--&gt;" not in out

    def test_no_html_escape_corruption_quotes(self):
        """Double quotes must not become &quot; in the output."""
        diagram = 'graph TD\n    A["Label with quotes"]'
        out = mermaid_to_html(diagram)
        assert "&quot;" not in out

    def test_strips_fences_before_encoding(self):
        """Fenced mermaid blocks must be stripped before base64 encoding."""
        fenced = "```mermaid\ngraph TD\n    A --> B\n```"
        plain = "graph TD\n    A --> B"
        out = mermaid_to_html(fenced)
        m = __import__("re").search(r'data-src="([^"]+)"', out)
        decoded = base64.b64decode(m.group(1)).decode("utf-8")
        assert decoded == plain

    def test_complex_flask_diagram_roundtrip(self):
        """Full flask diagram must survive sanitize + mermaid_to_html intact."""
        sanitized = sanitize_mermaid(FLASK_DIAGRAM)
        out = mermaid_to_html(sanitized)
        import re
        m = re.search(r'data-src="([^"]+)"', out)
        decoded = base64.b64decode(m.group(1)).decode("utf-8")
        # Key assertions on the decoded content
        assert 'subgraph "Web Server (WSGI)"' in decoded
        assert 'User["User/Client"]' in decoded
        assert 'Jinja2["Jinja2: Templating"]' in decoded
        assert "-->" in decoded
        assert "--&gt;" not in decoded
