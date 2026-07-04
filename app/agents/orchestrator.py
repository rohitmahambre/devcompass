from google.adk.agents import Agent
from google.genai import types as genai_types
from app.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT

from google.adk.agents.callback_context import CallbackContext

import json

import re

# Mermaid keywords that should never be treated as node IDs
_MERMAID_KEYWORDS = re.compile(
    r'^\s*(subgraph|end|graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap|timeline)\b',
    re.IGNORECASE
)

def sanitize_line(line: str) -> str:
    # Skip comment lines
    if line.strip().startswith("%%"):
        return line
    # Skip lines that already contain double quotes — they're already valid Mermaid
    # (e.g. subgraph "Web Server (WSGI)", or Node["Already quoted"])
    if '"' in line:
        return line
    # Skip structural keyword lines (subgraph, end, graph TD, etc.)
    if _MERMAID_KEYWORDS.match(line):
        return line
    # Apply bracket-quoting patterns — only match unquoted node labels
    patterns = [
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\(\[\s*([^\"\]\n]+?)\s*\]\)", r'\1\2(["\3"])'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\[\(\s*([^\"\)\n]+?)\s*\)\]", r'\1\2([("\3")])'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\[\[\s*([^\"\]\n]+?)\s*\]\]", r'\1\2[["\3"]]'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\(\(\s*([^\"\)\n]+?)\s*\)\)", r'\1\2(("\3"))'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\{\{\s*([^\"\}\n]+?)\s*\}\}", r'\1\2{{"\3"}}'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\[\s*([^\"\]\n]+?)\s*\]", r'\1\2["\3"]'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\(\s*([^\"\)\n]+?)\s*\)", r'\1\2("\3")'),
        (r"(^|\s|-->|---)\b([a-zA-Z0-9_-]+)\s*\{\s*([^\"\}\n]+?)\s*\}", r'\1\2{"\3"}'),
    ]
    for pattern, repl in patterns:
        line = re.sub(pattern, repl, line)
    return line

def sanitize_mermaid(diagram: str) -> str:
    if not diagram:
        return ""
    # Strip surrounding markdown fences if present
    stripped = diagram.strip()
    if stripped.startswith("```mermaid"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return "\n".join(sanitize_line(line) for line in stripped.splitlines())

async def unpack_ingestion_callback(callback_context: CallbackContext, llm_request=None) -> None:
    # before_model_callback fires before each LLM call made by the orchestrator.
    # Sub-agents in ADK write their structured output_schema results to session
    # events, not directly to session.state. This callback bridges that gap:
    # it scans completed events, extracts each sub-agent's output, and surfaces
    # them as top-level state keys so the orchestrator's system prompt can
    # reference {repo_path}, {file_tree}, etc. via ADK's {state_key} injection.

    # 1. Scan all session events to find outputs of completed sub-agents
    session = callback_context.session
    if session and session.events:
        for event in session.events:
            if event.partial:
                continue
            if event.output is not None:
                if event.author == "repo_ingestion_agent":
                    callback_context.state["repo_ingestion_result"] = event.output
                elif event.author == "architecture_analyst_agent":
                    output = event.output
                    if output:
                        if hasattr(output, "mermaid_diagram") and output.mermaid_diagram:
                            output.mermaid_diagram = sanitize_mermaid(output.mermaid_diagram)
                        elif isinstance(output, dict) and output.get("mermaid_diagram"):
                            output["mermaid_diagram"] = sanitize_mermaid(output["mermaid_diagram"])
                    callback_context.state["architecture_result"] = output
                elif event.author == "qa_agent":
                    callback_context.state["qa_result"] = event.output
                elif event.author == "documentation_generator_agent":
                    callback_context.state["documentation_result"] = event.output

    # 2. Extract keys from repo_ingestion_result and set them at top level
    result = callback_context.state.get("repo_ingestion_result")
    if not result:
        return None
        
    data = None
    if isinstance(result, dict):
        data = result
    elif isinstance(result, str):
        try:
            data = json.loads(result)
        except Exception:
            pass
    elif hasattr(result, "model_dump"):
        data = result.model_dump()
    elif hasattr(result, "dict"):
        data = result.dict()
    elif hasattr(result, "__dict__"):
        data = result.__dict__
        
    if isinstance(data, dict):
        for k, v in data.items():
            callback_context.state[k] = v
            
    return None

def create_orchestrator_agent(sub_agents: list) -> Agent:
    return Agent(
        name="orchestrator_agent",
        model="gemini-2.5-pro",
        description="Coordinates codebase analysis by routing tasks to specialized sub-agents.",
        instruction=ORCHESTRATOR_SYSTEM_PROMPT,
        sub_agents=sub_agents,
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
        ),
        before_model_callback=unpack_ingestion_callback,
        output_key="orchestrator_final_response",
    )
