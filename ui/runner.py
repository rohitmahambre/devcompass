import uuid
import asyncio
import os
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from app.agent import app

# Create a single global runner to persist sessions
session_service = InMemorySessionService()
runner = Runner(app=app, session_service=session_service, auto_create_session=True)

async def run_devcompass_analysis(repo_path_or_url: str, developer_role: str, session_id: str):
    """
    Run the full ingestion, architecture analysis, and documentation generation pipeline.
    Yields progress and updates outputs incrementally.
    """
    # 1. Construct the prompt for the orchestrator
    prompt = (
        f"Analyze the repository '{repo_path_or_url}' and generate all documentation artifacts "
        f"(readme, architecture, api_docs, onboarding_checklist) "
        f"personalized for a '{developer_role}' developer role."
    )
    
    # 2. Yield initial progress
    yield "⏳ Starting DevCompass codebase analysis...", "", "", "", "", ""
    
    # 3. Create the input message
    new_message = types.Content(parts=[types.Part.from_text(text=prompt)])
    
    # Initialize some progress indicators
    current_progress = "🔄 Processing request..."
    yield current_progress, "", "", "", "", ""
    
    try:
        # Run ADK agent tree
        async for event in runner.run_async(
            user_id="default",
            session_id=session_id,
            new_message=new_message
        ):
            # Check event details to update progress log
            author = getattr(event, 'author', '')
            if author:
                if author == 'repo_ingestion_agent':
                    current_progress = "✓ Repository Ingestion completed (indexing files, counting LOC)."
                elif author == 'architecture_analyst_agent':
                    current_progress = "✓ Software Architecture Analyzed (layers, module mappings)."
                elif author == 'documentation_generator_agent':
                    current_progress = "✓ Documentation Generated (README, ARCHITECTURE.md, onboarding checklist)."
                elif author == 'orchestrator_agent':
                    current_progress = "✓ Analysis session finished successfully."
                yield f"🔄 Running: {current_progress}", "", "", "", "", ""
                
    except Exception as e:
        yield f"❌ Error during codebase analysis: {str(e)}", "", "", "", "", ""
        return
        
    # 4. Fetch final state to display outputs
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    if not session:
        yield "❌ Error: Session state not found.", "", "", "", "", ""
        return
        
    state = session.state
    
    # Get Ingestion statistics
    ingestion = state.get("repo_ingestion_result", {})
    ingestion_summary = ""
    if ingestion:
        if isinstance(ingestion, dict):
            ingestion_summary = (
                f"### Repository Ingested\n"
                f"- **Languages/Frameworks**: {ingestion.get('detected_stack', {})}\n"
                f"- **Files**: {ingestion.get('total_files', 0)} files ({ingestion.get('total_lines', 0)} lines of code)\n"
                f"- **Primary Entry Points**: {', '.join(ingestion.get('entry_points', []))}"
            )
        else:
            # Pydantic model
            ingestion_summary = (
                f"### Repository Ingested\n"
                f"- **Languages/Frameworks**: {getattr(ingestion, 'detected_stack', {})}\n"
                f"- **Files**: {getattr(ingestion, 'total_files', 0)} files ({getattr(ingestion, 'total_lines', 0)} lines of code)\n"
                f"- **Primary Entry Points**: {', '.join(getattr(ingestion, 'entry_points', []))}"
            )
            
    # Get Architecture details
    arch = state.get("architecture_result", {})
    architecture_md = ""
    mermaid_md = ""
    if arch:
        summary = getattr(arch, 'architecture_summary', '') if not isinstance(arch, dict) else arch.get('architecture_summary', '')
        mermaid = getattr(arch, 'mermaid_diagram', '') if not isinstance(arch, dict) else arch.get('mermaid_diagram', '')
        
        # Format Mermaid for rendering in Markdown
        if mermaid:
            # Clean up wrap in mermaid block if not present
            if not mermaid.strip().startswith("```mermaid"):
                mermaid_md = f"```mermaid\n{mermaid}\n```"
            else:
                mermaid_md = mermaid
                
        # Structure summary
        architecture_md = f"### Architecture Narrative\n{summary}\n"
        
        # Design patterns and concerns
        patterns = getattr(arch, 'design_patterns', []) if not isinstance(arch, dict) else arch.get('design_patterns', [])
        concerns = getattr(arch, 'potential_concerns', []) if not isinstance(arch, dict) else arch.get('potential_concerns', [])
        
        if patterns:
            architecture_md += f"\n### Identified Design Patterns\n" + "\n".join(f"- {p}" for p in patterns)
        if concerns:
            architecture_md += f"\n### Onboarding / Architectural Concerns\n" + "\n".join(f"- {c}" for c in concerns)

    # Get Documentation
    docs = state.get("documentation_result", {})
    readme_content = ""
    arch_doc_content = ""
    checklist_content = ""
    
    if docs:
        readme_content = getattr(docs, 'readme_content', '') if not isinstance(docs, dict) else docs.get('readme_content', '')
        arch_doc_content = getattr(docs, 'architecture_doc_content', '') if not isinstance(docs, dict) else docs.get('architecture_doc_content', '')
        checklist_content = getattr(docs, 'onboarding_checklist_content', '') if not isinstance(docs, dict) else docs.get('onboarding_checklist_content', '')

    status_message = f"✅ Analysis Completed!\n\n{ingestion_summary}"
    yield status_message, architecture_md, mermaid_md, readme_content, arch_doc_content, checklist_content

async def run_chat_message(message: str, history: list, session_id: str):
    """
    Handle user follow-up questions about the codebase.
    """
    if not session_id:
        return "Please analyze a repository first before asking questions."
        
    # Check if session exists
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    if not session:
        return "Session not found. Please click 'Analyze Repository' to start a session."
        
    # Construct message Content
    new_message = types.Content(parts=[types.Part.from_text(text=message)])
    
    # Run the Q&A loop through Orchestrator
    try:
        async for event in runner.run_async(
            user_id="default",
            session_id=session_id,
            new_message=new_message
        ):
            pass
    except Exception as e:
        return f"Error executing Q&A agent: {str(e)}"
        
    # Get final answer from state
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    state = session.state
    
    # Retrieve Q&A agent output
    qa_res = state.get("qa_result", {})
    if qa_res:
        answer = getattr(qa_res, 'answer', '') if not isinstance(qa_res, dict) else qa_res.get('answer', '')
        ref_files = getattr(qa_res, 'referenced_files', []) if not isinstance(qa_res, dict) else qa_res.get('referenced_files', [])
        
        # Append references to response
        if ref_files:
            answer += "\n\n**Referenced Files:**\n"
            for ref in ref_files:
                path = ref.get('path', '')
                lines = ref.get('lines', '')
                answer += f"- `{os.path.basename(path)}` (Lines {lines})\n"
        return answer
        
    return "I couldn't generate an answer. Please try again."
