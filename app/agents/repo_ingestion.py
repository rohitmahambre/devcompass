import os
from google.adk.agents import Agent
from google.genai import types as genai_types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.schemas.ingestion import RepoIngestionOutput
from app.prompts.repo_ingestion import REPO_INGESTION_SYSTEM_PROMPT

def create_repo_ingestion_agent() -> Agent:
    # Dynamically locate the devcompass root directory to set PYTHONPATH
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    # tool_filter enforces least-privilege: the Repo Ingestion Agent only gets
    # the tools it needs to build an initial structural index. It does not get
    # search_codebase (reserved for Q&A/Architecture), get_commit_diff (reserved
    # for Q&A), or get_contributors (reserved for Documentation Generator).
    # This prevents the agent from making expensive cross-cutting searches during
    # the ingestion phase, which would inflate latency and cost.
    mcp_tools = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "devcompass_mcp.server"],
                env={"PYTHONPATH": root_dir},
            )
        ),
        tool_filter=[
            "read_file",
            "read_directory_tree",
            "detect_stack",
            "find_entry_points",
            "count_lines_of_code",
            "get_git_log",
            "clone_repository"
        ]
    )
    
    return Agent(
        name="repo_ingestion_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Ingests a repository (GitHub URL or local path) and builds a structural index.",
        instruction=REPO_INGESTION_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=RepoIngestionOutput,
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192
        )
    )
