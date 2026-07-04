import queue as stdlib_queue
import threading

import uuid
import asyncio
import os
import logging
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from app.agent import app
from app.agents.orchestrator import sanitize_mermaid

logger = logging.getLogger(__name__)

# Create a single global runner to persist sessions
session_service = InMemorySessionService()
runner = Runner(app=app, session_service=session_service, auto_create_session=True)

_SENTINEL = object()  # signals end of event stream


def _extract_state_from_events(events: list, state: dict) -> dict:
    """
    Walk ALL session events and pull sub-agent outputs into a plain dict.
    This is the fallback when the before_model_callback hasn't fired after
    the last sub-agent (which happens when the orchestrator ends without a
    final LLM call).
    """
    result = dict(state)  # start from existing state
    for event in events:
        if event.partial:
            continue
        if event.output is None:
            continue
        author = getattr(event, 'author', '') or ''
        if author == 'repo_ingestion_agent' and 'repo_ingestion_result' not in result:
            result['repo_ingestion_result'] = event.output
        elif author == 'architecture_analyst_agent' and 'architecture_result' not in result:
            result['architecture_result'] = event.output
        elif author == 'documentation_generator_agent' and 'documentation_result' not in result:
            result['documentation_result'] = event.output
        elif author == 'qa_agent' and 'qa_result' not in result:
            result['qa_result'] = event.output
    return result


def _run_adk_in_thread(prompt: str, session_id: str, event_queue: stdlib_queue.Queue):
    """
    Run the ADK pipeline in a dedicated thread with its own fresh event loop.
    This avoids the 'Task cannot await on itself' RuntimeError that occurs when
    ADK's _dynamic_node_scheduler re-enters the same asyncio task that Gradio is
    already driving.
    """
    async def _inner():
        new_message = types.Content(parts=[types.Part.from_text(text=prompt)])
        try:
            async for event in runner.run_async(
                user_id="default",
                session_id=session_id,
                new_message=new_message,
            ):
                event_queue.put(event)
        except Exception as exc:
            event_queue.put(exc)
        finally:
            event_queue.put(_SENTINEL)

    # Each thread gets a brand-new event loop — no sharing with Gradio's loop
    asyncio.run(_inner())


def _run_chat_in_thread(message: str, session_id: str, result_queue: stdlib_queue.Queue):
    """Same isolation for chat Q&A to avoid the same event-loop conflict."""
    async def _inner():
        new_message = types.Content(parts=[types.Part.from_text(text=message)])
        try:
            async for _ in runner.run_async(
                user_id="default",
                session_id=session_id,
                new_message=new_message,
            ):
                pass
        except Exception as exc:
            result_queue.put(exc)
            return
        finally:
            result_queue.put(_SENTINEL)

    asyncio.run(_inner())


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

    # Initialize some progress indicators
    current_progress = "🔄 Processing request..."
    yield current_progress, "", "", "", "", ""

    # 3. Kick off the ADK runner in a background thread
    event_queue: stdlib_queue.Queue = stdlib_queue.Queue()
    thread = threading.Thread(
        target=_run_adk_in_thread,
        args=(prompt, session_id, event_queue),
        daemon=True,
    )
    thread.start()

    try:
        while True:
            # Poll the queue without blocking the Gradio event loop
            try:
                item = event_queue.get(timeout=0.5)
            except stdlib_queue.Empty:
                # Yield a heartbeat so Gradio doesn't time out
                yield f"🔄 Running: {current_progress}", "", "", "", "", ""
                continue

            if item is _SENTINEL:
                break
            if isinstance(item, Exception):
                yield f"❌ Error during codebase analysis: {item}", "", "", "", "", ""
                return

            # item is an ADK Event
            author = getattr(item, 'author', '')
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

    finally:
        thread.join(timeout=5)

        
    # 4. Fetch final state — use both session.state AND event scan as fallback
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    if not session:
        yield "❌ Error: Session state not found.", "", "", "", "", ""
        return
        
    # Merge state from the callback + any events the callback missed
    state = _extract_state_from_events(session.events or [], session.state or {})
    
    logger.info("=== Final state keys: %s", list(state.keys()))
    
    # Get Ingestion statistics
    ingestion = state.get("repo_ingestion_result", {})
    ingestion_summary = ""
    if ingestion:
        if isinstance(ingestion, dict):
            stack = ingestion.get('detected_stack', {})
            total_files = ingestion.get('total_files', 0)
            total_lines = ingestion.get('total_lines', 0)
            entry_points = ingestion.get('entry_points', [])
        else:
            stack = getattr(ingestion, 'detected_stack', {})
            total_files = getattr(ingestion, 'total_files', 0)
            total_lines = getattr(ingestion, 'total_lines', 0)
            entry_points = getattr(ingestion, 'entry_points', [])

        # Format stack dict into readable strings
        if isinstance(stack, dict):
            langs = ', '.join(
                l.get('name', str(l)) if isinstance(l, dict) else str(l)
                for l in stack.get('languages', [])
            ) or '—'
            frameworks = ', '.join(stack.get('frameworks', [])) or '—'
            ci_cd = ', '.join(stack.get('ci_cd', [])) or '—'
            test_fw = ', '.join(stack.get('test_frameworks', [])) or '—'
            build = ', '.join(stack.get('build_tools', [])) or '—'
        else:
            langs = frameworks = ci_cd = test_fw = build = str(stack)

        ingestion_summary = (
            f"### ✅ Repository Ingested\n"
            f"| Property | Value |\n"
            f"|---|---|\n"
            f"| **Languages** | {langs} |\n"
            f"| **Frameworks** | {frameworks} |\n"
            f"| **Build Tools** | {build} |\n"
            f"| **CI/CD** | {ci_cd} |\n"
            f"| **Test Frameworks** | {test_fw} |\n"
            f"| **Files** | {total_files} files · {total_lines:,} lines of code |\n"
            f"| **Entry Points** | {', '.join(entry_points) or '—'} |"
        )

            
    # Get Architecture details
    arch = state.get("architecture_result", {})
    architecture_md = ""
    mermaid_md = ""
    if arch:
        summary = getattr(arch, 'architecture_summary', '') if not isinstance(arch, dict) else arch.get('architecture_summary', '')
        mermaid = getattr(arch, 'mermaid_diagram', '') if not isinstance(arch, dict) else arch.get('mermaid_diagram', '')
        mermaid = sanitize_mermaid(mermaid)
        mermaid_md = mermaid  # raw text; gradio_app wraps it via mermaid_to_html()
                
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

    logger.info("arch present: %s, docs present: %s, readme len: %d",
                bool(arch), bool(docs), len(readme_content))

    status_message = f"✅ Analysis Completed!\n\n{ingestion_summary}"
    yield status_message, architecture_md, mermaid_md, readme_content, arch_doc_content, checklist_content

async def run_chat_message(message: str, history: list, session_id: str):
    """
    Handle user follow-up questions about the codebase.
    Runs ADK in a dedicated thread to avoid event-loop conflicts with Gradio.
    """
    if not session_id:
        return "Please analyze a repository first before asking questions."
        
    # Check if session exists
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    if not session:
        return "Session not found. Please click 'Analyze Repository' to start a session."
    
    # Run Q&A in an isolated thread (same fix as analysis — avoids event-loop conflict)
    result_queue: stdlib_queue.Queue = stdlib_queue.Queue()
    thread = threading.Thread(
        target=_run_chat_in_thread,
        args=(message, session_id, result_queue),
        daemon=True,
    )
    thread.start()
    
    # Wait for the thread to finish (non-blocking via async sleep)
    while thread.is_alive():
        await asyncio.sleep(0.3)
    thread.join(timeout=5)
    
    # Check for errors put on the queue
    try:
        item = result_queue.get_nowait()
        if isinstance(item, Exception):
            return f"Error executing Q&A agent: {str(item)}"
    except stdlib_queue.Empty:
        pass
        
    # Get final answer from state
    session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
    if not session:
        return "I couldn't generate an answer. Please try again."

    state = _extract_state_from_events(session.events or [], session.state or {})
    
    # Retrieve Q&A agent output
    qa_res = state.get("qa_result", {})
    if qa_res:
        answer = getattr(qa_res, 'answer', '') if not isinstance(qa_res, dict) else qa_res.get('answer', '')
        ref_files = getattr(qa_res, 'referenced_files', []) if not isinstance(qa_res, dict) else qa_res.get('referenced_files', [])
        
        # Append references to response
        if ref_files:
            answer += "\n\n**Referenced Files:**\n"
            for ref in ref_files:
                path = ref.get('path', '') if isinstance(ref, dict) else getattr(ref, 'path', '')
                lines = ref.get('lines', '') if isinstance(ref, dict) else getattr(ref, 'lines', '')
                answer += f"- `{os.path.basename(str(path))}` (Lines {lines})\n"
        if answer:
            return answer
        
    return "I couldn't generate an answer. Please try again."
