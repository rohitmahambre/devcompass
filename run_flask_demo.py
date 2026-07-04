import asyncio
import os
import sys

# Ensure current directory is in Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.runner import run_devcompass_analysis, session_service

async def main():
    repo = "https://github.com/pallets/flask"
    role = "backend"
    session_id = "demo-session-flask"
    
    print(f"Starting DevCompass analysis for {repo} ({role} role)...")
    
    # Ensure environment variables are set
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    os.environ["GOOGLE_CLOUD_PROJECT"] = "gen-lang-client-0140337358"
    os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "flask_demo")
    os.makedirs(output_dir, exist_ok=True)
    
    async for status, arch_md, mermaid_md, readme, arch_doc, checklist in run_devcompass_analysis(repo, role, session_id):
        # Print status updates cleanly
        clean_status = status.split("\n\n")[0] if "\n\n" in status else status
        print(f"Status: {clean_status}")
        
        if "✅ Analysis Completed!" in status:
            # Debug session state
            session = await session_service.get_session(app_name="app", user_id="default", session_id=session_id)
            state = session.state
            print("\n--- DEBUG SESSION STATE ---")
            print(f"State keys: {list(state.keys())}")
            docs = state.get("documentation_result", {})
            print(f"documentation_result type: {type(docs)}")
            if hasattr(docs, "model_dump"):
                print(f"documentation_result dict: {docs.model_dump().keys()}")
                print(f"readme_content length: {len(getattr(docs, 'readme_content') or '')}")
                print(f"architecture_doc_content length: {len(getattr(docs, 'architecture_doc_content') or '')}")
                print(f"onboarding_checklist_content length: {len(getattr(docs, 'onboarding_checklist_content') or '')}")
            else:
                print(f"documentation_result value: {docs}")
            print("---------------------------\n")

            # Save files
            with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write(readme)
            with open(os.path.join(output_dir, "ARCHITECTURE.md"), "w", encoding="utf-8") as f:
                f.write(arch_doc)
            with open(os.path.join(output_dir, "architecture_overview.md"), "w", encoding="utf-8") as f:
                f.write(arch_md)
            with open(os.path.join(output_dir, "mermaid_diagram.txt"), "w", encoding="utf-8") as f:
                f.write(mermaid_md)
            with open(os.path.join(output_dir, "onboarding_checklist.md"), "w", encoding="utf-8") as f:
                f.write(checklist)
            print(f"\n🎉 Success! Saved all generated onboarding materials to: {output_dir}")
            print("Files generated:")
            print(f" - {os.path.join(output_dir, 'README.md')}")
            print(f" - {os.path.join(output_dir, 'ARCHITECTURE.md')}")
            print(f" - {os.path.join(output_dir, 'architecture_overview.md')}")
            print(f" - {os.path.join(output_dir, 'mermaid_diagram.txt')}")
            print(f" - {os.path.join(output_dir, 'onboarding_checklist.md')}")

if __name__ == "__main__":
    asyncio.run(main())
