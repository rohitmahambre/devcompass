import os
import uuid
import tempfile
import gradio as gr
import asyncio

from ui.runner import run_devcompass_analysis, run_chat_message

# We will store the paths to generated files globally or dynamically
class DocumentStore:
    def __init__(self):
        self.readme_path = None
        self.arch_path = None
        self.checklist_path = None

doc_store = DocumentStore()

def make_temp_file(content: str, filename: str) -> str:
    """Create a temporary file to make it downloadable."""
    if not content:
        return None
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

async def run_analysis_and_update_ui(repo_input, role_radio, session_id):
    """
    Triggers the analysis and updates all UI elements.
    """
    if not repo_input:
        yield (
            "⚠️ Please enter a repository URL or local path first.",
            "", "", "", "", "",
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        )
        return
        
    # We yield progress updates as they come from runner
    async for (
        status, arch_md, mermaid_md, readme, arch_doc, checklist
    ) in run_devcompass_analysis(repo_input, role_radio, session_id):
        
        # Prepare files if analysis is done (status starts with ✅ or final state exists)
        readme_file = None
        arch_file = None
        checklist_file = None
        
        if readme:
            doc_store.readme_path = make_temp_file(readme, "README.md")
            readme_file = doc_store.readme_path
        if arch_doc:
            doc_store.arch_path = make_temp_file(arch_doc, "ARCHITECTURE.md")
            arch_file = doc_store.arch_path
        if checklist:
            doc_store.checklist_path = make_temp_file(checklist, f"checklist_{role_radio}.md")
            checklist_file = doc_store.checklist_path
            
        # Determine visibility of download buttons
        readme_btn_update = gr.update(value=readme_file, visible=readme_file is not None)
        arch_btn_update = gr.update(value=arch_file, visible=arch_file is not None)
        checklist_btn_update = gr.update(value=checklist_file, visible=checklist_file is not None)
        
        yield (
            status,
            arch_md,
            mermaid_md,
            readme if readme else "Documentation is generating...",
            arch_doc if arch_doc else "Architecture documentation is generating...",
            checklist if checklist else "Personalized checklist is generating...",
            readme_btn_update,
            arch_btn_update,
            checklist_btn_update
        )

async def handle_chat(message, history, session_id):
    """
    Wrapper for handling Q&A chat messages.
    """
    # Message might be a dictionary or a ChatMessage object or a string depending on Gradio version
    message_text = ""
    if isinstance(message, dict):
        message_text = message.get("text", "")
    elif hasattr(message, "text"):
        message_text = message.text
    else:
        message_text = str(message)
        
    response = await run_chat_message(message_text, history, session_id)
    return response

# Custom JS to run mermaid initialization and rendering on markdown change
mermaid_js = """
head => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js';
    script.onload = () => {
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    };
    document.head.appendChild(script);
}
"""

def create_ui():
    with gr.Blocks(
        title="DevCompass 🧭 Codebase Intelligence",
        theme=gr.themes.Soft(primary_hue="teal", secondary_hue="indigo"),
        css=".mermaid { text-align: center; background: white; padding: 10px; border-radius: 8px; }"
    ) as demo:
        
        # Injected mermaid cdn
        gr.HTML(
            "<script src='https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js'></script>"
            "<script>mermaid.initialize({startOnLoad:true, theme:'neutral'});</script>"
        )
        
        gr.Markdown(
            "# DevCompass 🧭\n"
            "### AI-powered codebase intelligence for developer onboarding orientation."
        )
        
        # Session State variable
        session_id_state = gr.State(lambda: str(uuid.uuid4()))
        
        with gr.Row():
            repo_input = gr.Textbox(
                label="Repository Source",
                placeholder="Enter GitHub HTTPS URL (e.g. https://github.com/pallets/flask) or absolute local path...",
                scale=3
            )
            role_radio = gr.Radio(
                choices=["any", "backend", "frontend", "devops"],
                value="any",
                label="Developer Role",
                scale=1
            )
            
        with gr.Row():
            analyze_btn = gr.Button("Analyze Repository", variant="primary")
            clear_btn = gr.Button("Clear Input")
            
        progress_md = gr.Markdown("🟢 *Enter repository details and click Analyze to begin.*")
        
        with gr.Tabs() as main_tabs:
            with gr.Tab("Architecture Overview"):
                with gr.Row():
                    with gr.Column(scale=2):
                        architecture_md = gr.Markdown("The architecture summary will appear here after analysis.")
                    with gr.Column(scale=3):
                        gr.Markdown("### Repository Structural Diagram")
                        mermaid_md = gr.Markdown("Diagram will render here.")
                        
            with gr.Tab("Generated Docs"):
                with gr.Tabs():
                    with gr.Tab("README.md"):
                        readme_download = gr.DownloadButton("Download README.md", visible=False)
                        readme_preview = gr.Markdown("README preview will appear here.")
                    with gr.Tab("ARCHITECTURE.md"):
                        arch_doc_download = gr.DownloadButton("Download ARCHITECTURE.md", visible=False)
                        arch_doc_preview = gr.Markdown("ARCHITECTURE.md preview will appear here.")
                        
            with gr.Tab("Q&A Chat"):
                chat_interface = gr.ChatInterface(
                    fn=handle_chat,
                    additional_inputs=[session_id_state],
                    description="Ask questions about variables, modules, entrypoints, or requests flow inside the codebase."
                )
                
            with gr.Tab("Onboarding Checklist"):
                checklist_download = gr.DownloadButton("Download Onboarding Checklist", visible=False)
                checklist_md = gr.Markdown("Onboarding checklist will appear here.")

        # Bind events
        analyze_btn.click(
            fn=run_analysis_and_update_ui,
            inputs=[repo_input, role_radio, session_id_state],
            outputs=[
                progress_md,
                architecture_md,
                mermaid_md,
                readme_preview,
                arch_doc_preview,
                checklist_md,
                readme_download,
                arch_doc_download,
                checklist_download
            ]
        )
        
        # When mermaid markdown changes, trigger a JS rerender of mermaid graphs
        mermaid_md.change(
            fn=None,
            inputs=None,
            outputs=None,
            js="() => { setTimeout(() => { if (typeof mermaid !== 'undefined') { mermaid.run(); } }, 500); }"
        )
        
        # Clear inputs
        def clear_inputs():
            return "", "any", "🟢 *Enter repository details and click Analyze to begin.*", "", "", "", "", "", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
            
        clear_btn.click(
            fn=clear_inputs,
            inputs=None,
            outputs=[
                repo_input,
                role_radio,
                progress_md,
                architecture_md,
                mermaid_md,
                readme_preview,
                arch_doc_preview,
                checklist_md,
                readme_download,
                arch_doc_download,
                checklist_download
            ]
        )
        
    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(server_name="0.0.0.0", server_port=8080)
