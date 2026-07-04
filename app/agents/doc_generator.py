import os
from google.adk.agents import Agent
from google.genai import types as genai_types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.schemas.docs import DocGeneratorOutput
from app.prompts.doc_generator import DOC_GENERATOR_SYSTEM_PROMPT

def create_doc_generator_agent() -> Agent:
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
            "get_contributors"
        ]
    )
    
    return Agent(
        name="documentation_generator_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Generates README, ARCHITECTURE.md, API docs, and onboarding checklists.",
        instruction=DOC_GENERATOR_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=DocGeneratorOutput,
        output_key="documentation_result",
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=16384
        )
    )
