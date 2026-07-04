# DevCompass 🧭

> **AI-powered codebase intelligence for developer onboarding.** Point it at any GitHub repository and get architecture diagrams, generated documentation, and a personalized onboarding checklist — in minutes, not weeks.

Built with [Google ADK](https://adk.dev/), Gemini 2.5, and a custom MCP server for secure read-only codebase analysis.

---

## The Problem

A new developer joins a team and is handed a 50,000-line codebase. No recent architecture doc, a stale README, and their first PR is due Friday. This is the developer onboarding tax — and it costs engineering teams weeks of lost productivity per hire.

Existing tools don't solve this:
- **GitHub Copilot / IDEs**: require you to already know which file to open
- **grep / ctags**: search-oriented, cannot explain *why* something exists
- **AI chat assistants**: limited context windows, no cross-file reasoning, no deliverable generation

## The Solution

DevCompass is a **multi-agent AI system** that ingests any repository and produces:

1. **Architecture Overview** — narrative + Mermaid diagram of the codebase layers
2. **Generated README** — accurate, auto-generated from the actual source
3. **ARCHITECTURE.md** — module responsibilities, design patterns, data flow
4. **Onboarding Checklist** — role-specific (backend/frontend/devops) day-by-day guide
5. **Q&A Chat** — natural language questions answered with file + line references

Why agents? Because onboarding is inherently multi-step: *first* understand the structure, *then* analyze architecture, *then* generate documentation. A single LLM call cannot traverse an entire repository, reason across file boundaries, and produce deliverables simultaneously. Agents can.

---

## Architecture

```
User (Gradio UI)
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                            │
│  gemini-2.5-pro │ Routes tasks, manages session state           │
└──────┬────────────────┬────────────────┬──────────────┬─────────┘
       │                │                │              │
       ▼                ▼                ▼              ▼
┌────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────┐
│    Repo    │  │ Architecture │  │   Q&A    │  │ Documentation  │
│ Ingestion  │  │   Analyst    │  │  Agent   │  │   Generator    │
│   Agent    │  │   Agent      │  │          │  │    Agent       │
│            │  │              │  │          │  │                │
│ flash-2.5  │  │  pro-2.5     │  │ flash-2.5│  │  pro-2.5       │
└─────┬──────┘  └──────┬───────┘  └────┬─────┘  └───────┬────────┘
      │                │               │                 │
      └────────────────┴───────────────┴─────────────────┘
                                │
                    ┌───────────────────────┐
                    │  devcompass-mcp-server │
                    │                       │
                    │  File Tools (4)        │
                    │  Git Tools  (4)        │
                    │  Analysis Tools (4)    │
                    └───────────────────────┘
                                │
                    ┌───────────────────────┐
                    │  Target Repository    │
                    │  (GitHub clone / local│
                    │   path — read-only)   │
                    └───────────────────────┘
```

### Agent Responsibilities

| Agent | Model | Role | Tools Available |
|---|---|---|---|
| Orchestrator | gemini-2.5-pro | Routes user intent to sub-agents; synthesizes final output | None (delegates only) |
| Repo Ingestion | gemini-2.5-flash | Clones repo, builds file index, detects stack, reads key files | clone, read_file, read_directory_tree, detect_stack, find_entry_points, count_loc, get_git_log |
| Architecture Analyst | gemini-2.5-pro | Identifies layers, generates Mermaid diagram, flags design concerns | read_file, search_codebase, read_directory_tree, get_file_metadata |
| Q&A Agent | gemini-2.5-flash | Answers natural language questions with file/line citations | search_codebase, read_file, get_file_metadata, get_recent_changes, get_contributors |
| Documentation Generator | gemini-2.5-pro | Produces README, ARCHITECTURE.md, onboarding checklist | read_file, search_codebase, get_contributors |

### MCP Server — Security-First Design

The custom `devcompass-mcp-server` exposes 12 read-only tools:

**File Tools**: `read_file`, `read_directory_tree`, `search_codebase`, `get_file_metadata`

**Git Tools**: `get_git_log`, `get_recent_changes`, `get_contributors`, `get_commit_diff`

**Analysis Tools**: `detect_stack`, `find_entry_points`, `count_lines_of_code`, `clone_repository`

Security constraints enforced at every tool call:
- Path traversal prevention via `pathlib.Path.resolve()` + `is_relative_to()`
- Blocked file list: `.env`, `credentials.json`, `id_rsa`, `*.pem`, `*.key`, and any filename matching `*secret*`, `*password*`, `*credential*`
- `.gitignore`-aware directory traversal (respects the repo's own ignore rules)
- No code execution — all tools are strictly read-only
- Each agent receives only the tools it needs (`tool_filter` principle of least privilege)

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent framework | [Google ADK](https://adk.dev/) 2.0+ |
| LLM | Gemini 2.5 Pro (reasoning) + Gemini 2.5 Flash (throughput) |
| MCP server | [FastMCP](https://github.com/jlowin/fastmcp) via `python-mcp` |
| UI | [Gradio](https://gradio.app/) 5.0+ |
| Git analysis | [GitPython](https://gitpython.readthedocs.io/) |
| Gitignore parsing | [pathspec](https://python-path-specification.readthedocs.io/) |
| Packaging | [uv](https://docs.astral.sh/uv/) |
| Deployment | Google Cloud Run |
| Agent CLI | [google-agents-cli](https://pypi.org/project/google-agents-cli/) |

---

## Quick Start (Local)

### Prerequisites

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [google-agents-cli](https://pypi.org/project/google-agents-cli/): `uv tool install google-agents-cli`
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Setup

```bash
git clone https://github.com/<your-username>/devcompass
cd devcompass

# Install dependencies
agents-cli install

# Configure your API key
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_key_here
```

### Run the Gradio UI

```bash
uv run python -m ui.gradio_app
# Open http://localhost:8080
```

### Run via agents-cli playground (ADK web UI)

```bash
agents-cli playground
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes (AI Studio) | Gemini API key from Google AI Studio |
| `GOOGLE_CLOUD_PROJECT` | For GCP | GCP project ID (auto-detected on Cloud Run) |
| `GOOGLE_CLOUD_LOCATION` | No | Region for Vertex AI (default: `global`) |
| `ALLOW_ORIGINS` | No | Comma-separated CORS origins for FastAPI |
| `LOGS_BUCKET_NAME` | No | GCS bucket for ADK artifact storage |

---

## Running Tests

```bash
# Unit tests
uv run pytest tests/unit

# Integration tests (requires GOOGLE_API_KEY)
uv run pytest tests/integration

# Agent evaluation
agents-cli eval run --eval_set tests/eval/datasets/basic-dataset.json
```

---

## Docker

```bash
# Build
docker build -t devcompass .

# Run
docker run -p 8080:8080 -e GOOGLE_API_KEY=your_key devcompass

# Open http://localhost:8080
```

---

## Deploy to Google Cloud Run

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# One-command deploy via agents-cli
agents-cli deploy

# Or manually
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/devcompass
gcloud run deploy devcompass \
  --image gcr.io/YOUR_PROJECT_ID/devcompass \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-secrets GOOGLE_API_KEY=GOOGLE_API_KEY:latest
```

To add CI/CD and Terraform infrastructure:
```bash
agents-cli scaffold enhance
agents-cli infra cicd
```

---

## Project Structure

```
devcompass/
├── app/
│   ├── agent.py                    # Root agent assembly + ADK App
│   ├── agents/
│   │   ├── orchestrator.py         # Orchestrator agent (gemini-2.5-pro)
│   │   ├── repo_ingestion.py       # Repo ingestion agent (gemini-2.5-flash)
│   │   ├── architecture_analyst.py # Architecture analyst (gemini-2.5-pro)
│   │   ├── qa_agent.py             # Q&A agent (gemini-2.5-flash)
│   │   └── doc_generator.py        # Documentation generator (gemini-2.5-pro)
│   ├── prompts/                    # System prompts for each agent
│   ├── schemas/                    # Pydantic I/O schemas for typed agent output
│   ├── app_utils/                  # Telemetry + typing utilities
│   └── fast_api_app.py             # ADK FastAPI app (for agents-cli / GCP)
├── devcompass_mcp/
│   ├── server.py                   # FastMCP server entry point (12 tools)
│   ├── security.py                 # Path validation, blocked file list
│   └── tools/
│       ├── file_tools.py           # File reading + search tools
│       ├── git_tools.py            # Git history tools
│       └── analysis_tools.py       # Stack detection + entry point tools
├── ui/
│   ├── gradio_app.py               # Gradio UI (4-tab layout)
│   └── runner.py                   # ADK session runner + progress streaming
├── tests/
│   ├── unit/                       # Unit tests (security, tools)
│   ├── integration/                # End-to-end agent tests
│   └── eval/datasets/              # ADK eval datasets
├── Dockerfile                      # Container for Cloud Run deployment
├── agents-cli-manifest.yaml        # agents-cli project configuration
└── pyproject.toml                  # Dependencies (uv)
```

---

## Observability

Built-in OpenTelemetry instrumentation exports traces to Cloud Trace and logs to Cloud Logging when deployed on GCP. Configure via `app/app_utils/telemetry.py`.

---

## Competition

Built for the [AI Agents: Intensive Vibe Coding Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project) by Google on Kaggle.

**Track:** Agents for Business

**Key concepts demonstrated:**
- Multi-agent system with Google ADK (5 agents, typed I/O, session state)
- Custom MCP Server (12 tools, security-enforced read-only access)
- Security features (path traversal prevention, credential file blocking)
- Deployability (Docker + Cloud Run + agents-cli deploy)
- Agent Skills CLI (agents-cli-manifest.yaml, eval datasets)
- Antigravity (used to generate this codebase from the technical specification)
