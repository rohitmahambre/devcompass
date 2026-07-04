import os
from google.adk.agents import Agent
from google.genai import types as genai_types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.schemas.architecture import ArchitectureAnalystOutput
from app.prompts.architecture_analyst import ARCHITECTURE_ANALYST_SYSTEM_PROMPT

def create_architecture_analyst_agent() -> Agent:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
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
            "search_codebase",
            "read_directory_tree",
            "get_file_metadata"
        ]
    )
    
    return Agent(
        name="architecture_analyst_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Analyzes the software architecture, identifies layers, and outputs a Mermaid diagram.",
        instruction=ARCHITECTURE_ANALYST_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=ArchitectureAnalystOutput,
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192
        )
    )
