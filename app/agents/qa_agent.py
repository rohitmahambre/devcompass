import os
from google.adk.agents import Agent
from google.genai import types as genai_types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.schemas.qa import QAAgentOutput
from app.prompts.qa_agent import QA_AGENT_SYSTEM_PROMPT

def create_qa_agent() -> Agent:
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
            "search_codebase",
            "read_file",
            "get_file_metadata",
            "get_recent_changes",
            "get_contributors"
        ]
    )
    
    return Agent(
        name="qa_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Answers questions about code structure and behavior, and performs codebase review.",
        instruction=QA_AGENT_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=QAAgentOutput,
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192
        )
    )
