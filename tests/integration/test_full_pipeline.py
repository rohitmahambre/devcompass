import pytest
import os
import shutil
import uuid
import asyncio
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from app.agent import app

@pytest.fixture
def integration_sample_repo():
    root_dir = "/tmp/devcompass/integration_sample_repo"
    os.makedirs(root_dir, exist_ok=True)
    
    # Create a small Flask app structure
    with open(os.path.join(root_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("flask==3.0.0\n")
        
    with open(os.path.join(root_dir, "app.py"), "w", encoding="utf-8") as f:
        f.write(
            "from flask import Flask\n"
            "app = Flask(__name__)\n\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'Hello World'\n\n"
            "if __name__ == '__main__':\n"
            "    app.run()\n"
        )
        
    with open(os.path.join(root_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Integration Sample\nThis is a sample project.\n")
        
    yield root_dir
    
    if os.path.exists(root_dir):
        shutil.rmtree(root_dir)

@pytest.mark.asyncio
async def test_end_to_end_analysis(integration_sample_repo):
    session_service = InMemorySessionService()
    runner = Runner(app=app, session_service=session_service, auto_create_session=True)
    session_id = str(uuid.uuid4())
    
    # Prompt the orchestrator to perform full onboarding analysis on the local repository
    prompt = (
        f"Analyze the repository '{integration_sample_repo}' and generate all documentation "
        f"artifacts (readme, architecture, api_docs, onboarding_checklist) "
        f"for developer role 'backend'."
    )
    
    new_message = types.Content(parts=[types.Part.from_text(text=prompt)])
    
    # Execute the pipeline
    # Collect all events
    events = []
    async for event in runner.run_async(
        user_id="default",
        session_id=session_id,
        new_message=new_message
    ):
        events.append(event)
        
    # Get session state
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    assert session is not None
    
    state = session.state
    
    # Verify Ingestion results
    assert "repo_ingestion_result" in state
    ingest = state["repo_ingestion_result"]
    
    # Handle both dict and Pydantic object
    repo_path = ingest.get("repo_path") if isinstance(ingest, dict) else getattr(ingest, "repo_path", "")
    assert repo_path == integration_sample_repo
    
    # Verify Architecture results
    assert "architecture_result" in state
    arch = state["architecture_result"]
    mermaid = arch.get("mermaid_diagram") if isinstance(arch, dict) else getattr(arch, "mermaid_diagram", "")
    assert "graph TD" in mermaid
    
    # Verify Documentation results
    assert "documentation_result" in state
    docs = state["documentation_result"]
    readme_content = docs.get("readme_content") if isinstance(docs, dict) else getattr(docs, "readme_content", "")
    checklist_content = docs.get("onboarding_checklist_content") if isinstance(docs, dict) else getattr(docs, "onboarding_checklist_content", "")
    
    assert readme_content is not None
    assert len(readme_content) > 0
    assert checklist_content is not None
    assert len(checklist_content) > 0
