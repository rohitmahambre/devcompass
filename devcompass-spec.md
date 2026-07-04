# DevCompass: Technical Specification

**AI Agents: Intensive Vibe Coding Capstone Project — Google Kaggle Competition**
**Track:** Agents for Business
**Deadline:** July 6, 2026
**Author:** rohitmahambre@gmail.com
**Version:** 1.0 — July 1, 2026

---

## Table of Contents

1. [Project Overview & Name Rationale](#1-project-overview--name-rationale)
2. [Problem Statement](#2-problem-statement)
3. [Agent Architecture](#3-agent-architecture)
4. [MCP Server Design](#4-mcp-server-design)
5. [State Management](#5-state-management)
6. [Security Design](#6-security-design)
7. [User Interface](#7-user-interface)
8. [Tech Stack](#8-tech-stack)
9. [Project File Structure](#9-project-file-structure)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Kaggle Evaluation Mapping](#11-kaggle-evaluation-mapping)
12. [6-Day Implementation Plan](#12-6-day-implementation-plan)
13. [Demo Script](#13-demo-script)

---

## 1. Project Overview & Name Rationale

### What is DevCompass?

DevCompass is a multi-agent AI system that acts as an intelligent onboarding guide for software repositories. Given a GitHub URL or a local path, DevCompass autonomously ingests the codebase, reasons about its structure, generates documentation, answers natural language questions, performs code review, and produces a personalized developer onboarding checklist.

It is designed for teams that want to dramatically reduce the time a new developer spends becoming productive on an unfamiliar codebase — from weeks to hours.

### Why "DevCompass" and Not "CodeOracle"

The name "DevCompass" was chosen deliberately over alternatives like "CodeOracle" or "RepoMind":

- **Oracle implies mystery and prophecy.** An oracle speaks from inscrutable knowledge. That framing is exactly wrong for a developer tool — developers need to trust, audit, and understand the reasoning behind every output.
- **Compass implies navigation and orientation.** A compass does not tell you what to think; it tells you where you are and helps you find your way. DevCompass orients a developer within an unfamiliar codebase — it maps the terrain and provides practical direction.
- **"Dev" grounds it in its audience.** The word "developer" frames this as a practitioner's tool, not an abstract AI product. It belongs in a terminal, a workflow, a PR review process.
- **Compasses are read-only instruments.** A compass observes and reports; it does not modify the environment. This mirrors DevCompass's core security guarantee: read-only analysis, no code execution.

### Core Capabilities at a Glance

| Capability | Output |
|---|---|
| Repository ingestion | File tree, language/framework detection, entry point map |
| Architecture analysis | Mermaid diagram, layer breakdown, module responsibility table |
| Q&A | Natural language answers with file+line references |
| Documentation generation | README.md, ARCHITECTURE.md, API reference |
| Code review | Bugs, security issues, anti-patterns with severity ratings |
| Onboarding checklist | Personalized step-by-step guide for a new developer |

---

## 2. Problem Statement

### The Onboarding Tax

When a developer joins a new project or is handed an unfamiliar repository, they typically spend 1–3 weeks in an unproductive orientation phase before making meaningful contributions. During this period they are:

- Manually tracing call stacks to understand control flow
- Reading stale or absent documentation that may describe a prior version of the system
- Asking teammates repetitive questions that interrupt productive work
- Inferring conventions from inconsistent examples scattered across the codebase
- Discovering entry points, configuration files, and environment requirements by trial and error

This tax is paid repeatedly: every new hire, every team rotation, every open-source contributor who wants to submit a patch.

### Why Existing Tools Fall Short

| Tool | Limitation |
|---|---|
| GitHub Copilot | Autocompletes at the cursor; requires you to already be in the right file. Does not reason across files. |
| ChatGPT / Claude | Can answer questions about code snippets you paste; cannot autonomously traverse a full repository. |
| Static documentation (wikis) | Written once, rarely updated. Describes intent, not current reality. |
| grep / ctags / LSP | Require you to know what you are looking for. Cannot explain *why* something exists. |
| AI code search (e.g., Sourcegraph Cody) | Search-oriented; does not synthesize cross-cutting architecture understanding or generate deliverables. |

### The Gap DevCompass Fills

No current tool:
1. **Autonomously traverses** a full repository without requiring the user to specify which files to read
2. **Reasons across file boundaries** to understand layering, dependencies, and conventions
3. **Generates deliverables** (documentation, diagrams, checklists) rather than just answering questions
4. **Maintains a shared mental model** of the codebase that multiple specialized agents can query

DevCompass addresses all four gaps using a multi-agent architecture where specialized agents collaborate through shared session state and a purpose-built MCP server.

### Target Users

- **New hires** who need to become productive on a large existing codebase
- **Open-source contributors** evaluating whether and how to contribute
- **Tech leads** who need to quickly audit an acquired or inherited codebase
- **Security reviewers** who need a rapid first-pass analysis before a deep audit
- **Developer experience teams** who want to automate the generation of onboarding documentation

---

## 3. Agent Architecture

DevCompass uses five Google ADK agents arranged in a two-tier hierarchy: one orchestrator that receives user intent and four specialist sub-agents. The orchestrator delegates tasks using ADK's `mode="task"` delegation pattern, which gives each sub-agent typed input/output schemas and keeps the orchestrator in control throughout the session.

### Architecture Diagram

```
User (Gradio UI)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                  Orchestrator Agent                      │
│  - Receives user intent (repo URL + question/task)       │
│  - Manages delegation sequence                           │
│  - Synthesizes final output for UI                       │
│  - Writes to session state: orchestration_plan           │
└──────┬──────────────┬──────────────┬──────────┬─────────┘
       │              │              │          │
       ▼              ▼              ▼          ▼
 ┌──────────┐  ┌──────────────┐  ┌────────┐  ┌───────────────┐
 │  Repo    │  │ Architecture │  │  Q&A   │  │Documentation  │
 │Ingestion │  │  Analyst     │  │ Agent  │  │  Generator    │
 │  Agent   │  │   Agent      │  │        │  │    Agent      │
 └──────────┘  └──────────────┘  └────────┘  └───────────────┘
       │              │              │                │
       └──────────────┴──────────────┴────────────────┘
                              │
                    ┌─────────────────┐
                    │   MCP Server    │
                    │  (devcompass-   │
                    │   mcp-server)   │
                    │                 │
                    │ File tools      │
                    │ Git tools       │
                    │ Analysis tools  │
                    └─────────────────┘
                              │
                    ┌─────────────────┐
                    │  GitHub MCP     │
                    │  Server         │
                    │  (official)     │
                    └─────────────────┘
```

### State Flow

```
Session State (ADK InMemorySessionService / VertexAiSessionService)

repo_path          → set by Repo Ingestion Agent, read by all others
file_tree          → set by Repo Ingestion Agent, read by all others
detected_stack     → set by Repo Ingestion Agent, read by all others
entry_points       → set by Repo Ingestion Agent, read by Architect + Q&A
architecture_doc   → set by Architecture Analyst, read by Doc Generator
code_review        → set by Q&A Agent (when review mode), read by Doc Generator
onboarding_checklist → set by Doc Generator, written to artifact
generated_readme   → set by Doc Generator, written to artifact
```

---

### 3.1 Orchestrator Agent

**Role:** The single point of contact for user intent. Determines which sub-agents to run and in what order, based on the user's request. Synthesizes final output and manages the overall session.

**Model:** `gemini-2.5-pro` — chosen because orchestration requires the highest reasoning quality. The orchestrator must interpret ambiguous user intent, plan a delegation sequence, and synthesize coherent output from multiple sub-agent results. Flash is insufficient for this level of judgment.

**Input:** User's natural language request + optional repo URL or local path

**Output:** Structured session plan + final synthesized response rendered in the UI

**Tools:** None directly. Uses `request_task_repo_ingestion_agent`, `request_task_architecture_analyst_agent`, `request_task_qa_agent`, `request_task_documentation_generator_agent` (auto-generated by ADK from `mode="task"` sub-agents).

**System Prompt Outline:**

```
You are DevCompass Orchestrator, the coordination center of a multi-agent codebase analysis system.

When given a repository URL or path and a user goal, you:
1. Confirm the repository has been ingested (check session state for `repo_path`).
   If not, always start by delegating to the Repo Ingestion Agent.
2. Based on the user's goal, choose a delegation sequence:
   - "Understand architecture" → Repo Ingestion → Architecture Analyst
   - "Generate documentation" → Repo Ingestion → Architecture Analyst → Documentation Generator
   - "Answer a question" → Repo Ingestion → Q&A Agent
   - "Full onboarding" → Repo Ingestion → Architecture Analyst → Q&A Agent (for review) → Documentation Generator
3. Delegate using the request_task_* tools in sequence.
4. Synthesize a final response that presents the outputs clearly.

Rules:
- Never skip Repo Ingestion for a new repository.
- If repo_path is already in state, skip re-ingestion unless explicitly asked.
- Always report progress to the user as each agent completes.
- If a sub-agent fails, report the error and ask the user how to proceed.
- Never attempt to read files directly — delegate to sub-agents.
```

**ADK Definition:**

```python
from google.adk.agents import Agent
from google.genai import types as genai_types

def create_orchestrator_agent(sub_agents: list) -> Agent:
    return Agent(
        name="orchestrator_agent",
        model="gemini-2.5-pro",
        description="Coordinates codebase analysis by routing tasks to specialized sub-agents.",
        instruction=ORCHESTRATOR_SYSTEM_PROMPT,  # full prompt from above
        sub_agents=sub_agents,
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,  # deterministic planning
            max_output_tokens=4096,
        ),
        output_key="orchestrator_final_response",
    )
```

---

### 3.2 Repo Ingestion Agent

**Role:** The first agent to run for any new repository. Clones the repo (if URL given) or validates the local path, then builds a complete index of the codebase: file tree, language/framework detection, key file content, entry points, and dependency manifest summary.

**Model:** `gemini-2.5-flash` — the ingestion task involves reading many files and building a structured index. It is a high-throughput, structured extraction task that does not require deep reasoning. Flash's larger token throughput and lower cost are ideal here.

**Input (task schema):**

```python
from pydantic import BaseModel, Field
from typing import Optional

class RepoIngestionInput(BaseModel):
    repo_url: Optional[str] = Field(
        None,
        description="GitHub URL to clone, e.g. https://github.com/owner/repo"
    )
    local_path: Optional[str] = Field(
        None,
        description="Absolute path to a local repository directory"
    )
    max_file_size_kb: int = Field(
        100,
        description="Skip files larger than this size in kilobytes"
    )
```

**Output (task schema):**

```python
class RepoIngestionOutput(BaseModel):
    repo_path: str = Field(description="Absolute path to the ingested repository on disk")
    file_tree: str = Field(description="ASCII tree of the repository file structure")
    detected_stack: dict = Field(description="Detected languages, frameworks, and build tools")
    entry_points: list[str] = Field(description="Identified entry point files (main.py, index.js, etc.)")
    dependency_summary: str = Field(description="Summary of dependencies from manifest files")
    key_files_content: dict[str, str] = Field(description="Content of critical files: README, config, entrypoints")
    total_files: int
    total_lines: int
```

**Tools (via MCP):**
- `read_directory_tree` — builds the file tree
- `detect_stack` — reads package.json, requirements.txt, Cargo.toml, pom.xml, go.mod
- `find_entry_points` — identifies main files, CLI entrypoints, server start files
- `read_file` — reads key files: README, config files, primary entrypoints
- `count_lines_of_code` — aggregates LOC statistics
- `get_git_log` — retrieves recent commit history for context

**System Prompt Outline:**

```
You are the Repo Ingestion Agent for DevCompass.

Your task: given a repository path or URL, build a complete structural index.

Steps:
1. If a URL is given, use clone_repository tool to clone to /tmp/devcompass/<repo-name>.
   If a local path is given, validate it exists and is a git repository.
2. Use read_directory_tree to get the full file structure. Store this.
3. Use detect_stack to identify languages and frameworks. Store this.
4. Use find_entry_points to identify primary entry files. Store this.
5. Read the following key files if they exist (use read_file):
   - README.md, README.rst (any format)
   - package.json, requirements.txt, pyproject.toml, Cargo.toml, pom.xml, go.mod
   - .env.example (NOT .env)
   - docker-compose.yml, Dockerfile
   - The top 3 entry point files identified in step 4
6. Use count_lines_of_code to get aggregate statistics.
7. Use get_git_log to get the last 10 commits for context.

Output a complete RepoIngestionOutput. Be precise — other agents depend on this index.

Rules:
- Never read .env files. Skip them if encountered.
- Skip binary files, images, and files over max_file_size_kb.
- Do not summarize or interpret — produce raw structured data.
```

**ADK Definition:**

```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

def create_repo_ingestion_agent() -> Agent:
    mcp_tools = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "devcompass_mcp.server"],
                env={"PYTHONPATH": "/app"},
            )
        ),
        tool_filter=[
            "read_directory_tree",
            "detect_stack",
            "find_entry_points",
            "read_file",
            "count_lines_of_code",
            "get_git_log",
            "clone_repository",
        ],
    )
    return Agent(
        name="repo_ingestion_agent",
        model="gemini-2.5-flash",
        mode="task",
        description="Ingests a repository and builds a structural index of its contents.",
        instruction=REPO_INGESTION_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=RepoIngestionOutput,
        output_key="repo_ingestion_result",
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192,
        ),
    )
```

---

### 3.3 Architecture Analyst Agent

**Role:** Receives the repo index built by the Ingestion Agent and performs deep architectural reasoning: identifies software layers (API, service, data, UI), maps module responsibilities, traces data flows between key components, and produces a Mermaid diagram.

**Model:** `gemini-2.5-pro` — architecture analysis is the highest-judgment task after orchestration. The agent must reason about design patterns (MVC, hexagonal, microservices), infer intent from naming and structure, and synthesize a coherent architectural narrative. This requires Pro.

**Input (task schema):**

```python
class ArchitectureAnalystInput(BaseModel):
    repo_path: str
    file_tree: str
    detected_stack: dict
    entry_points: list[str]
    specific_question: Optional[str] = Field(
        None,
        description="Optional: a specific architectural question to focus on"
    )
```

**Output (task schema):**

```python
class ArchitectureAnalystOutput(BaseModel):
    architecture_summary: str = Field(
        description="2-3 paragraph narrative description of the architecture"
    )
    layers: list[dict] = Field(
        description="List of identified layers, each with name, description, and files"
    )
    module_responsibilities: list[dict] = Field(
        description="Each module/package with its responsibility and key files"
    )
    data_flow: str = Field(
        description="Description of how data flows through the system"
    )
    mermaid_diagram: str = Field(
        description="Valid Mermaid graph TD diagram of the architecture"
    )
    design_patterns: list[str] = Field(
        description="Identified design patterns (e.g. Repository, Factory, Observer)"
    )
    potential_concerns: list[str] = Field(
        description="Architectural concerns worth noting for a new developer"
    )
```

**Tools (via MCP):**
- `read_file` — reads specific files to understand module logic
- `search_codebase` — grepping for patterns (e.g., `@app.route`, `class.*Service`, `import`)
- `read_directory_tree` — scoped tree reads for specific directories
- `get_file_metadata` — checks file sizes and modification dates for recency context

**System Prompt Outline:**

```
You are the Architecture Analyst Agent for DevCompass.

Given a repository index, perform deep architectural analysis.

Your analysis process:
1. Read the file tree and detected stack to form initial hypotheses about architecture style.
2. Use search_codebase to find architectural markers:
   - Route definitions (@app.route, @GetMapping, router.get, etc.)
   - Class hierarchies (class.*Service, class.*Repository, class.*Controller)
   - Configuration files (application.yml, settings.py, config.ts)
   - Test structure (tests/, __tests__/, spec/)
3. Read 5-10 key files to validate your hypotheses:
   - Entry points, primary service classes, data models, API handlers
4. Identify the architectural pattern: MVC, Clean Architecture, Hexagonal, Microservices, etc.
5. Map each directory/module to its responsibility.
6. Trace one complete data flow from external request to data persistence.
7. Generate a Mermaid diagram using graph TD syntax.

Mermaid diagram rules:
- Use subgraph blocks for each layer
- Show directional arrows for dependencies and data flow
- Include only the top-level components (max 15 nodes)
- Use descriptive node labels

Output a complete ArchitectureAnalystOutput.
```

**ADK Definition:**

```python
def create_architecture_analyst_agent() -> Agent:
    mcp_tools = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "devcompass_mcp.server"],
                env={"PYTHONPATH": "/app"},
            )
        ),
        tool_filter=["read_file", "search_codebase", "read_directory_tree", "get_file_metadata"],
    )
    return Agent(
        name="architecture_analyst_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Analyzes repository architecture, identifies layers, and generates diagrams.",
        instruction=ARCHITECTURE_ANALYST_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=ArchitectureAnalystOutput,
        output_key="architecture_result",
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )
```

---

### 3.4 Code Q&A Agent

**Role:** Answers specific natural language questions about the codebase. Can also perform targeted code review when asked. Uses the repo index from session state plus targeted file reads via MCP tools to find and explain specific code.

**Model:** `gemini-2.5-flash` — Q&A is inherently iterative and interactive. The user asks questions in a chat loop, so latency matters. Flash provides fast responses while still being capable of following code logic across multiple files. For complex review tasks, it can read many files rapidly.

**Input (task schema):**

```python
class QAAgentInput(BaseModel):
    question: str = Field(description="The user's natural language question about the codebase")
    mode: str = Field(
        "qa",
        description="'qa' for question answering, 'review' for code review"
    )
    focus_path: Optional[str] = Field(
        None,
        description="Optional: limit analysis to a specific directory or file"
    )
```

**Output (task schema):**

```python
class QAAgentOutput(BaseModel):
    answer: str = Field(description="The answer to the user's question")
    referenced_files: list[dict] = Field(
        description="Files referenced, each with path and relevant line range"
    )
    code_snippets: list[dict] = Field(
        description="Relevant code snippets with file path and line numbers"
    )
    follow_up_suggestions: list[str] = Field(
        description="Suggested follow-up questions the user might want to ask"
    )
    # Only populated when mode='review'
    review_findings: Optional[list[dict]] = Field(
        None,
        description="Code review findings with severity, category, file, line, description"
    )
```

**Tools (via MCP):**
- `search_codebase` — finds relevant code by keyword/regex
- `read_file` — reads specific files for detailed analysis
- `get_file_metadata` — gets file info without full content
- `get_recent_changes` — understands what changed recently (for "why does X work this way?" context)
- `get_contributors` — identifies who owns which parts of the code

**System Prompt Outline:**

```
You are the Code Q&A Agent for DevCompass.

You have access to a fully ingested repository. Session state contains:
- repo_path: the repository location
- file_tree: complete file structure
- detected_stack: languages and frameworks
- entry_points: main entry files

For Q&A mode:
1. Parse the question to identify: what entity is being asked about (function, class, file, concept)
2. Use search_codebase to find relevant code locations
3. Read the relevant files with read_file
4. Formulate a precise answer with exact file paths and line references
5. Never invent code — only cite what you read

For review mode:
1. Identify the scope (whole repo or focus_path)
2. Read all files in scope systematically
3. Flag issues in these categories:
   - Security: hardcoded credentials, injection vulnerabilities, insecure defaults
   - Bugs: null pointer risks, off-by-one, unreachable code, type mismatches
   - Anti-patterns: god classes, circular imports, hardcoded config values
   - Performance: N+1 queries, unbounded loops, unnecessary allocations
4. Rate each finding: CRITICAL, HIGH, MEDIUM, LOW

Always cite your sources with file paths and line numbers.
If you cannot find the answer, say so explicitly — never hallucinate code.
```

**ADK Definition:**

```python
def create_qa_agent() -> Agent:
    mcp_tools = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "devcompass_mcp.server"],
                env={"PYTHONPATH": "/app"},
            )
        ),
        tool_filter=[
            "search_codebase",
            "read_file",
            "get_file_metadata",
            "get_recent_changes",
            "get_contributors",
        ],
    )
    return Agent(
        name="qa_agent",
        model="gemini-2.5-flash",
        mode="task",
        description="Answers natural language questions about codebase structure and behavior.",
        instruction=QA_AGENT_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=QAAgentOutput,
        output_key="qa_result",
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )
```

---

### 3.5 Documentation Generator Agent

**Role:** The final agent in the standard pipeline. Synthesizes all prior outputs (repo index, architecture analysis, Q&A/review results) into polished deliverables: a README, an ARCHITECTURE.md, an API reference, and a personalized developer onboarding checklist.

**Model:** `gemini-2.5-pro` — documentation generation is a writing task that requires high-quality prose, clear structure, and the ability to synthesize complex technical information into something readable by a newcomer. Pro delivers markedly better writing quality for this task.

**Input (task schema):**

```python
class DocGeneratorInput(BaseModel):
    requested_artifacts: list[str] = Field(
        description="List of documents to generate: 'readme', 'architecture', 'api_docs', 'onboarding_checklist'"
    )
    developer_role: Optional[str] = Field(
        None,
        description="Role of the new developer for checklist personalization: 'frontend', 'backend', 'fullstack', 'devops'"
    )
    existing_readme: Optional[str] = Field(
        None,
        description="Existing README content to improve rather than replace"
    )
```

**Output (task schema):**

```python
class DocGeneratorOutput(BaseModel):
    readme_content: Optional[str] = Field(None, description="Generated README.md in markdown")
    architecture_doc_content: Optional[str] = Field(None, description="Generated ARCHITECTURE.md in markdown")
    api_docs_content: Optional[str] = Field(None, description="Generated API reference in markdown")
    onboarding_checklist_content: Optional[str] = Field(None, description="Personalized onboarding checklist in markdown")
    artifacts_generated: list[str] = Field(description="Names of artifacts successfully generated")
```

**Tools (via MCP):**
- `read_file` — reads any additional files needed for documentation (e.g., OpenAPI specs, docstrings)
- `search_codebase` — finds exported functions/classes for API docs
- `get_contributors` — credits contributors in documentation

**State Read (injected via `{state_key}` in instruction):**
- `{repo_ingestion_result}` — file tree, stack, entry points
- `{architecture_result}` — architecture narrative, layers, Mermaid diagram
- `{qa_result}` — code review findings (if performed)

**System Prompt Outline:**

```
You are the Documentation Generator Agent for DevCompass.

You have access to the full analysis results from prior agents via session state.

Available context (injected from session state):
- Repo ingestion result: {repo_ingestion_result}
- Architecture analysis: {architecture_result}
- Q&A / review results: {qa_result}

For each requested artifact:

README.md:
- Project title and one-sentence description
- Badges (build status, language, license if detectable)
- Prerequisites and installation steps
- Quick start (the minimal steps to run the project)
- Project structure overview (top-level directories explained)
- Configuration reference (environment variables from .env.example)
- Contributing guidelines

ARCHITECTURE.md:
- Architecture overview (from architecture_result.architecture_summary)
- Embedded Mermaid diagram (from architecture_result.mermaid_diagram)
- Layer descriptions (from architecture_result.layers)
- Module responsibility table
- Data flow description
- Design patterns in use
- Known architectural concerns

API Docs:
- Search for exported functions, routes, and classes
- Document each with signature, parameters, return type, and description
- Group by module

Onboarding Checklist:
- Day 1: Environment setup (prerequisites, clone, dependencies, first run)
- Week 1: Understanding the codebase (read these files in this order)
- Week 1: First contribution (find a good first issue area)
- Personalize based on developer_role if provided

Write in clear, precise technical English. Use markdown. Include code blocks.
```

**ADK Definition:**

```python
def create_documentation_generator_agent() -> Agent:
    mcp_tools = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "devcompass_mcp.server"],
                env={"PYTHONPATH": "/app"},
            )
        ),
        tool_filter=["read_file", "search_codebase", "get_contributors"],
    )
    return Agent(
        name="documentation_generator_agent",
        model="gemini-2.5-pro",
        mode="task",
        description="Generates README, architecture docs, and onboarding checklists from analysis results.",
        instruction=DOC_GENERATOR_SYSTEM_PROMPT,
        tools=[mcp_tools],
        output_schema=DocGeneratorOutput,
        output_key="documentation_result",
        generate_content_config=genai_types.GenerateContentConfig(
            temperature=0.3,  # slightly higher for better prose quality
            max_output_tokens=16384,
        ),
    )
```

---

### 3.6 Agent Assembly (root_agent)

```python
# app/agent.py
from google.adk.agents import Agent
from .agents.orchestrator import create_orchestrator_agent
from .agents.repo_ingestion import create_repo_ingestion_agent
from .agents.architecture_analyst import create_architecture_analyst_agent
from .agents.qa_agent import create_qa_agent
from .agents.doc_generator import create_documentation_generator_agent

def build_root_agent() -> Agent:
    # Build sub-agents (factory functions avoid "agent already has parent" error)
    repo_ingestion = create_repo_ingestion_agent()
    architect = create_architecture_analyst_agent()
    qa = create_qa_agent()
    doc_gen = create_documentation_generator_agent()

    # Assemble orchestrator with sub-agents
    orchestrator = create_orchestrator_agent(
        sub_agents=[repo_ingestion, architect, qa, doc_gen]
    )
    return orchestrator

root_agent = build_root_agent()
```

---

## 4. MCP Server Design

DevCompass includes a custom MCP server (`devcompass-mcp-server`) implemented in Python using the `mcp` library. It exposes read-only tools for file system access, git metadata, and static analysis. It also connects to the official GitHub MCP server for repository metadata.

The server runs as a stdio subprocess managed by ADK's `McpToolset`. In production (Cloud Run), it runs as a sidecar process started via the container entrypoint script.

### 4.1 Server Bootstrap

```python
# devcompass_mcp/server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from .tools import (
    file_tools,
    git_tools,
    analysis_tools,
)

server = Server("devcompass-mcp")

# Register all tools
for tool_fn in file_tools + git_tools + analysis_tools:
    server.register_tool(tool_fn)

async def main():
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1])

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 4.2 File Tools

#### `read_file`

**Description:** Read the content of a single file. Enforces path safety and file type allowlist.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Absolute path to the file to read"
    },
    "encoding": {
      "type": "string",
      "enum": ["utf-8", "latin-1"],
      "default": "utf-8"
    },
    "max_lines": {
      "type": "integer",
      "description": "Maximum number of lines to return. Omit for full file.",
      "default": 2000
    },
    "start_line": {
      "type": "integer",
      "description": "1-indexed line to start reading from",
      "default": 1
    }
  },
  "required": ["path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "content": {"type": "string"},
    "total_lines": {"type": "integer"},
    "truncated": {"type": "boolean"},
    "path": {"type": "string"}
  }
}
```

**Security notes:**
- Resolves symlinks and validates the canonical path is within `repo_root` (path traversal prevention)
- Rejects files matching BLOCKED_PATTERNS: `*.env`, `.env*`, `*.pem`, `*.key`, `*.p12`, `*secret*`, `*credential*`, `*password*`
- Rejects binary files (checks for null bytes in first 512 bytes)
- Max file size: 500 KB

**Implementation:**
```python
import os
import pathlib

BLOCKED_PATTERNS = [".env", "*.pem", "*.key", "*.p12", ".git/config"]
BLOCKED_NAMES = {".env", "credentials.json", "secrets.yaml", "secrets.yml"}

def is_path_safe(requested_path: str, repo_root: str) -> bool:
    """Prevent path traversal: ensure canonical path is within repo_root."""
    canonical = pathlib.Path(requested_path).resolve()
    root = pathlib.Path(repo_root).resolve()
    return canonical.is_relative_to(root)

def is_blocked(path: str) -> bool:
    name = pathlib.Path(path).name
    if name in BLOCKED_NAMES:
        return True
    for pattern in BLOCKED_PATTERNS:
        if pathlib.Path(path).match(pattern):
            return True
    return False
```

---

#### `read_directory_tree`

**Description:** Return an ASCII or JSON tree of a directory, respecting .gitignore rules.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "Absolute path to directory root"},
    "max_depth": {"type": "integer", "default": 6},
    "include_hidden": {"type": "boolean", "default": false},
    "format": {"type": "string", "enum": ["ascii", "json"], "default": "ascii"}
  },
  "required": ["path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "tree": {"type": "string", "description": "ASCII or JSON tree representation"},
    "total_files": {"type": "integer"},
    "total_dirs": {"type": "integer"},
    "gitignore_applied": {"type": "boolean"}
  }
}
```

**Security notes:**
- Uses `gitpython` to parse `.gitignore` and exclude ignored files
- Skips `.git/` directory entirely
- `include_hidden=false` by default (skips dot-files other than .gitignore, .env.example)
- Maximum 50,000 files before truncation

---

#### `search_codebase`

**Description:** Search for a pattern (literal string or regex) across files in the repository. Returns matches with file paths and line numbers.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "pattern": {"type": "string", "description": "Search pattern (supports regex)"},
    "path": {"type": "string", "description": "Root path to search within"},
    "file_extensions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Filter to specific extensions, e.g. ['.py', '.ts']"
    },
    "is_regex": {"type": "boolean", "default": false},
    "case_sensitive": {"type": "boolean", "default": true},
    "max_results": {"type": "integer", "default": 50},
    "context_lines": {"type": "integer", "default": 2}
  },
  "required": ["pattern", "path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "matches": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file": {"type": "string"},
          "line": {"type": "integer"},
          "match": {"type": "string"},
          "context_before": {"type": "string"},
          "context_after": {"type": "string"}
        }
      }
    },
    "total_matches": {"type": "integer"},
    "truncated": {"type": "boolean"}
  }
}
```

**Security notes:**
- Pattern is compiled with `re.compile` in a try/except; invalid regex returns an error
- Regex complexity limit: rejects patterns with 100+ character alternations (ReDoS prevention)
- All file paths in results are validated against repo root

---

#### `get_file_metadata`

**Description:** Return metadata about a file without reading its content.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"}
  },
  "required": ["path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"},
    "size_bytes": {"type": "integer"},
    "last_modified": {"type": "string", "format": "datetime"},
    "language": {"type": "string"},
    "line_count": {"type": "integer"},
    "is_binary": {"type": "boolean"}
  }
}
```

---

### 4.3 Git Tools

#### `get_git_log`

**Description:** Return recent commit history from the repository's git log.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "max_commits": {"type": "integer", "default": 20},
    "author": {"type": "string", "description": "Filter by author email or name"},
    "since": {"type": "string", "description": "ISO date, e.g. 2024-01-01"}
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "commits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "hash": {"type": "string"},
          "short_hash": {"type": "string"},
          "author": {"type": "string"},
          "date": {"type": "string"},
          "message": {"type": "string"},
          "files_changed": {"type": "integer"}
        }
      }
    }
  }
}
```

**Security notes:** Reads git metadata only. Does not expose remote URLs or credentials stored in git config. The `[credential]` section of `.git/config` is never returned.

---

#### `get_recent_changes`

**Description:** Return a summary of files changed in the last N commits.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "num_commits": {"type": "integer", "default": 10}
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "changed_files": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "change_count": {"type": "integer"},
          "last_changed_by": {"type": "string"},
          "last_changed_at": {"type": "string"}
        }
      }
    }
  }
}
```

---

#### `get_contributors`

**Description:** Return contributor statistics from git history.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "max_contributors": {"type": "integer", "default": 20}
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "contributors": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "email": {"type": "string"},
          "commit_count": {"type": "integer"},
          "first_commit": {"type": "string"},
          "last_commit": {"type": "string"}
        }
      }
    }
  }
}
```

---

#### `get_commit_diff`

**Description:** Return the diff for a specific commit.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "commit_hash": {"type": "string"},
    "max_diff_lines": {"type": "integer", "default": 500}
  },
  "required": ["repo_path", "commit_hash"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "diff": {"type": "string"},
    "files_changed": {"type": "array", "items": {"type": "string"}},
    "truncated": {"type": "boolean"}
  }
}
```

**Security notes:** Commit hash is validated against `^[a-f0-9]{4,40}$` to prevent shell injection. Uses gitpython (not subprocess shell invocation).

---

### 4.4 Analysis Tools

#### `detect_stack`

**Description:** Detect programming languages, frameworks, and build tools used in the repository by reading manifest files.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"}
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "languages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
          "detected_from": {"type": "string"}
        }
      }
    },
    "frameworks": {"type": "array", "items": {"type": "string"}},
    "build_tools": {"type": "array", "items": {"type": "string"}},
    "test_frameworks": {"type": "array", "items": {"type": "string"}},
    "container": {"type": "string", "description": "Docker, Podman, or null"},
    "ci_cd": {"type": "array", "items": {"type": "string"}}
  }
}
```

**Detection logic:**

| File | Detected stack component |
|---|---|
| `package.json` | Node.js; checks `dependencies` for React, Vue, Next.js, Express |
| `requirements.txt`, `pyproject.toml` | Python; scans for Django, Flask, FastAPI, SQLAlchemy |
| `pom.xml`, `build.gradle` | Java/Kotlin; scans for Spring Boot, Quarkus |
| `Cargo.toml` | Rust; scans for tokio, actix-web, axum |
| `go.mod` | Go; scans for gin, echo, fiber |
| `.github/workflows/*.yml` | GitHub Actions |
| `Dockerfile` | Docker |
| `docker-compose.yml` | Docker Compose |
| `*.tf` | Terraform |

---

#### `find_entry_points`

**Description:** Identify likely entry point files — the files a developer would run to start the application.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "detected_stack": {
      "type": "object",
      "description": "Output from detect_stack, used to narrow search"
    }
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "entry_points": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "type": {"type": "string", "enum": ["main", "cli", "server", "test_runner", "build_script"]},
          "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
          "reason": {"type": "string"}
        }
      }
    }
  }
}
```

**Detection heuristics:**
- Python: `if __name__ == "__main__"`, `main.py`, `app.py`, `manage.py`, `cli.py`
- Node.js: `main` field in `package.json`, `index.js`, `server.js`, `bin/` directory
- Java: classes with `public static void main`, Spring Boot `@SpringBootApplication`
- Go: `func main()` in `main.go`
- Rust: `fn main()` in `src/main.rs`
- Generic: `Makefile` targets, `scripts/` directory

---

#### `count_lines_of_code`

**Description:** Count lines of code by language, excluding comments and blank lines where possible.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "repo_path": {"type": "string"},
    "include_tests": {"type": "boolean", "default": true}
  },
  "required": ["repo_path"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "total_lines": {"type": "integer"},
    "total_files": {"type": "integer"},
    "by_language": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "files": {"type": "integer"},
          "lines": {"type": "integer"},
          "blank": {"type": "integer"},
          "comment": {"type": "integer"}
        }
      }
    }
  }
}
```

---

#### `clone_repository`

**Description:** Clone a public GitHub repository to a local temporary directory. For private repos, requires a GitHub token in environment.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "url": {"type": "string", "description": "HTTPS GitHub URL"},
    "target_dir": {"type": "string", "description": "Directory to clone into", "default": "/tmp/devcompass"}
  },
  "required": ["url"]
}
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "local_path": {"type": "string"},
    "repo_name": {"type": "string"},
    "default_branch": {"type": "string"},
    "clone_time_seconds": {"type": "number"}
  }
}
```

**Security notes:**
- URL validated against `^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$`
- No SSH URLs (prevent arbitrary host connections)
- `--depth 1` (shallow clone) to limit data ingestion
- Clones to `/tmp/devcompass/<repo-name>` only; no user-controlled target paths
- `GITHUB_TOKEN` sourced from environment, never from user input

---

## 5. State Management

DevCompass uses ADK's session state to share context between agents within a single analysis session. The state is structured as a flat key-value store with clear naming conventions.

### State Schema

```python
# State keys written by each agent
# Convention: <agent_name>_<data_name>

SESSION_STATE_SCHEMA = {
    # Written by Repo Ingestion Agent
    "repo_path": str,                    # Absolute path to ingested repo
    "file_tree": str,                    # ASCII tree of repo structure
    "detected_stack": dict,              # Languages, frameworks, tools
    "entry_points": list[dict],          # Entry point files with metadata
    "dependency_summary": str,           # Summary of dependencies
    "key_files_content": dict[str, str], # Critical file contents
    "total_files": int,
    "total_lines": int,

    # Written by Architecture Analyst Agent
    "architecture_result": dict,         # Full ArchitectureAnalystOutput

    # Written by Q&A Agent
    "qa_result": dict,                   # Latest QAAgentOutput

    # Written by Documentation Generator Agent
    "documentation_result": dict,        # DocGeneratorOutput with artifact refs

    # Written by Orchestrator
    "orchestrator_final_response": str,  # Final synthesized response for UI
    "analysis_progress": list[str],      # Progress log for UI streaming
}
```

### State Injection in Agent Instructions

ADK supports `{state_key}` placeholders in agent instructions. The Documentation Generator uses this to receive prior outputs without tool calls:

```python
DOC_GENERATOR_SYSTEM_PROMPT = """
You are the Documentation Generator Agent for DevCompass.

Repository information:
- Stack: {detected_stack}
- File tree: {file_tree}
- Entry points: {entry_points}

Architecture analysis results:
{architecture_result}

Code review results (if available):
{qa_result}

Generate the requested documentation artifacts using this context.
"""
```

### Progress Tracking

The Orchestrator writes to `analysis_progress` after each sub-agent completes. The Gradio UI polls this key to display real-time progress:

```python
# In orchestrator system prompt / callback
async def update_progress(callback_context, message: str):
    progress = callback_context.state.get("analysis_progress", [])
    progress.append({"timestamp": datetime.utcnow().isoformat(), "message": message})
    callback_context.state["analysis_progress"] = progress
```

### Session Service

- **Development:** `InMemorySessionService()` — fast, no persistence
- **Production (Cloud Run):** `InMemorySessionService()` — DevCompass is stateless by design. Each analysis is a new session. No cross-session persistence is needed or desired.

```python
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.apps import App

session_service = InMemorySessionService()
app = App(name="app", root_agent=root_agent)
runner = Runner(app=app, session_service=session_service)
```

### Context Caching

The repo index (file tree + detected stack) is large and read by multiple agents. ADK's context caching is enabled to reduce API cost:

```python
from google.adk.agents.context_cache_config import ContextCacheConfig

app = App(
    name="app",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=4096,
        ttl_seconds=3600,  # 1 hour — longer than typical session
        cache_intervals=5,
    ),
)
```

---

## 6. Security Design

DevCompass is a read-only analysis tool. Security is not an afterthought — it is a core design constraint that shapes every tool and agent in the system.

### 6.1 No Code Execution

DevCompass never executes any code from the analyzed repository. This is enforced at multiple levels:

- **ADK agents** do not use `BuiltInCodeExecutor` or `VertexAiCodeExecutor`
- **MCP tools** perform only file reads and git metadata queries — no subprocess execution of repository code
- **Docker container** runs with `--read-only` filesystem for the repository mount
- **System prompts** explicitly instruct agents: "Never execute code from the repository"

### 6.2 Secret File Filtering

The MCP `read_file` tool maintains a blocklist of sensitive file patterns:

```python
BLOCKED_EXACT_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    "credentials.json",
    "serviceAccountKey.json",
    "secrets.yaml",
    "secrets.yml",
    "id_rsa",
    "id_ed25519",
    ".netrc",
    ".npmrc",  # may contain registry tokens
})

BLOCKED_EXTENSIONS = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".crt",
    ".jks", ".keystore",
})

BLOCKED_PATTERNS = [
    re.compile(r".*secret.*", re.IGNORECASE),
    re.compile(r".*password.*", re.IGNORECASE),
    re.compile(r".*credential.*", re.IGNORECASE),
    re.compile(r".*token.*\.(json|yml|yaml)$", re.IGNORECASE),
]
```

Files matching `.gitignore` patterns are additionally excluded from `read_directory_tree` output, so agents never see their existence in the tree.

### 6.3 Path Traversal Prevention

Every MCP tool that accepts a file path validates the canonical path before reading:

```python
def validate_path(requested_path: str, repo_root: str) -> str:
    """
    Resolve symlinks and verify the canonical path is within repo_root.
    Raises ValueError on traversal attempt.
    """
    canonical = pathlib.Path(requested_path).resolve()
    root = pathlib.Path(repo_root).resolve()

    if not canonical.is_relative_to(root):
        raise ValueError(
            f"Path traversal attempt: {requested_path} resolves to {canonical}, "
            f"which is outside repo root {root}"
        )
    return str(canonical)
```

This prevents `../../etc/passwd` style attacks regardless of how an agent constructs the path.

### 6.4 API Key Management

All credentials are injected via environment variables and never appear in code, agent instructions, or session state:

| Secret | Environment Variable | Used By |
|---|---|---|
| Gemini API key | `GOOGLE_API_KEY` | ADK agents |
| GitHub token (optional, for private repos) | `GITHUB_TOKEN` | MCP `clone_repository` tool |
| Google Cloud project | `GOOGLE_CLOUD_PROJECT` | Vertex AI (prod) |

The `.env` file format is used for local development only. In Cloud Run, secrets are injected via Secret Manager references in the service definition.

### 6.5 No Data Persistence

DevCompass does not store any repository content beyond the lifetime of a single session:

- Cloned repositories are written to `/tmp/devcompass/` and deleted after the session ends (cleanup hook in Gradio)
- Session state uses `InMemorySessionService` — no database writes
- No artifact service configured in production — generated docs are returned directly to the UI and not stored server-side
- Generated documentation is presented to the user for download; DevCompass does not retain copies

### 6.6 Private Repository Handling

For private repositories:
1. The user must clone locally and provide the local path — DevCompass never requests GitHub credentials on behalf of the user
2. If a GitHub token is provided in environment (`GITHUB_TOKEN`), `clone_repository` uses it for HTTPS authentication via git credential store — the token is never logged or returned in tool output
3. The cloned directory is chmod 700 and only accessible to the process user

### 6.7 Input Validation

- Repository URLs: validated against `^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$`
- Local paths: must exist, must be a directory, must contain a `.git` directory
- Search patterns: regex validated, complexity-limited (prevents ReDoS)
- Commit hashes: validated against `^[a-f0-9]{4,40}$`
- All integer parameters: range-limited (max_depth ≤ 20, max_results ≤ 500, etc.)

---

## 7. User Interface

DevCompass uses Gradio for its web UI. The UI is deliberately minimal — it gets out of the way and lets the multi-agent output speak for itself.

### 7.1 Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  DevCompass  🧭  Codebase Intelligence for Developers            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Repository                                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ GitHub URL or local path...                                │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [Analyze Repository]  [Clear]                                   │
│                                                                  │
│  Developer Role (for onboarding checklist):                     │
│  ( ) Any  (●) Backend  ( ) Frontend  ( ) DevOps                 │
│                                                                  │
│  ────────── Progress ──────────────────────────────────────────  │
│  ✓ Repository ingested (47 files, Python/FastAPI)                │
│  ✓ Architecture analyzed (3 layers identified)                   │
│  ⟳ Generating documentation...                                   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  Architecture Overview │ Generated Docs │ Q&A Chat │ Checklist   │
│ ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  [Tab content area]                                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 Tab: Architecture Overview

- Architecture narrative (markdown rendered)
- Mermaid diagram (rendered via `gr.Markdown` with mermaid.js CDN)
- Layer table (name, description, key files)
- Module responsibility table
- Design patterns and concerns

### 7.3 Tab: Generated Docs

Three sub-tabs: README | ARCHITECTURE.md | API Docs

For each:
- Full markdown preview rendered in `gr.Markdown`
- Download button (`gr.DownloadButton`) for the raw `.md` file
- Copy-to-clipboard button (JavaScript)

### 7.4 Tab: Q&A Chat

- `gr.ChatInterface` component
- User asks questions in natural language
- Each answer shows referenced files as expandable callouts
- Code snippets rendered with syntax highlighting
- Follow-up suggestions displayed as clickable buttons

### 7.5 Tab: Onboarding Checklist

- Interactive checklist (markdown rendered with checkboxes)
- Personalized by developer role
- Download as `.md` file
- Progress tracker showing completion percentage

### 7.6 Gradio Implementation Sketch

```python
# app/ui.py
import gradio as gr
import asyncio
from .runner import run_devcompass_analysis

def create_ui():
    with gr.Blocks(
        title="DevCompass",
        theme=gr.themes.Soft(),
        css="footer {display: none}",
    ) as demo:
        gr.Markdown("# DevCompass\nCo-pilot for understanding unfamiliar codebases.")

        with gr.Row():
            repo_input = gr.Textbox(
                label="Repository",
                placeholder="https://github.com/owner/repo or /path/to/local/repo",
                scale=4,
            )
            role_radio = gr.Radio(
                ["any", "backend", "frontend", "devops"],
                label="Developer Role",
                value="any",
                scale=1,
            )

        with gr.Row():
            analyze_btn = gr.Button("Analyze Repository", variant="primary")
            clear_btn = gr.Button("Clear")

        progress_md = gr.Markdown("*Enter a repository URL or path above to begin.*")

        with gr.Tabs() as output_tabs:
            with gr.Tab("Architecture Overview"):
                architecture_md = gr.Markdown()
                mermaid_md = gr.Markdown()

            with gr.Tab("Generated Docs"):
                with gr.Tabs():
                    with gr.Tab("README.md"):
                        readme_preview = gr.Markdown()
                        readme_download = gr.DownloadButton("Download README.md")
                    with gr.Tab("ARCHITECTURE.md"):
                        arch_doc_preview = gr.Markdown()
                        arch_doc_download = gr.DownloadButton("Download ARCHITECTURE.md")

            with gr.Tab("Q&A Chat"):
                chat = gr.ChatInterface(
                    fn=handle_chat_message,
                    type="messages",
                )

            with gr.Tab("Onboarding Checklist"):
                checklist_md = gr.Markdown()
                checklist_download = gr.DownloadButton("Download Checklist")

        analyze_btn.click(
            fn=run_analysis_and_update_ui,
            inputs=[repo_input, role_radio],
            outputs=[
                progress_md,
                architecture_md,
                mermaid_md,
                readme_preview,
                arch_doc_preview,
                checklist_md,
            ],
        )

    return demo
```

---

## 8. Tech Stack

### 8.1 Core Components

| Component | Technology | Justification |
|---|---|---|
| Multi-agent orchestration | Google ADK (Python) | Required by competition; provides `mode="task"`, session state, MCP integration |
| Primary LLM (reasoning) | Gemini 2.5 Pro | Best-in-class for architecture synthesis, doc generation, orchestration |
| Primary LLM (throughput) | Gemini 2.5 Flash | Higher token throughput and lower cost for file reading and Q&A |
| Custom MCP server | Python `mcp` library | Provides file/git/analysis tools with security enforcement |
| External MCP server | GitHub official MCP server | Repo metadata: stars, issues, PR list, topics |
| Web UI | Gradio 5.x | Fast to build; renders markdown natively; `ChatInterface` for Q&A |
| Containerization | Docker | Cloud Run requirement |
| Deployment | Google Cloud Run | Serverless; scales to zero; competition-aligned |
| Session state | ADK `InMemorySessionService` | Stateless design; no database needed |

### 8.2 Python Dependencies

```toml
# pyproject.toml
[project]
name = "devcompass"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "google-adk>=1.0.0",
    "google-genai>=1.0.0",
    "mcp>=1.0.0",
    "gitpython>=3.1.0",
    "gradio>=5.0.0",
    "pydantic>=2.0.0",
    "pathspec>=0.12.0",   # .gitignore parsing
    "chardet>=5.0.0",     # binary file detection
    "pygments>=2.18.0",   # syntax highlighting metadata
    "uvicorn>=0.30.0",    # ASGI server for Cloud Run
    "fastapi>=0.111.0",   # ADK uses FastAPI under the hood
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

### 8.3 Environment Variables

```bash
# Required
GOOGLE_API_KEY=                     # Gemini API key (dev via AI Studio)
GOOGLE_CLOUD_PROJECT=               # GCP project ID (prod)
GOOGLE_CLOUD_LOCATION=us-central1   # Vertex AI region (prod)
GOOGLE_GENAI_USE_VERTEXAI=False     # Set True in prod

# Optional
GITHUB_TOKEN=                       # For private repo cloning
DEVCOMPASS_MAX_REPO_SIZE_MB=500     # Reject repos larger than this
DEVCOMPASS_WORK_DIR=/tmp/devcompass # Working directory for clones
LOG_LEVEL=INFO
```

---

## 9. Project File Structure

```
devcompass/
│
├── app/                            # ADK agent package (name must match App(name="app"))
│   ├── __init__.py
│   ├── agent.py                    # root_agent definition (entry point for ADK)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # create_orchestrator_agent()
│   │   ├── repo_ingestion.py       # create_repo_ingestion_agent()
│   │   ├── architecture_analyst.py # create_architecture_analyst_agent()
│   │   ├── qa_agent.py             # create_qa_agent()
│   │   └── doc_generator.py        # create_documentation_generator_agent()
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── ingestion.py            # RepoIngestionInput, RepoIngestionOutput
│   │   ├── architecture.py         # ArchitectureAnalystInput, ArchitectureAnalystOutput
│   │   ├── qa.py                   # QAAgentInput, QAAgentOutput
│   │   └── docs.py                 # DocGeneratorInput, DocGeneratorOutput
│   ├── prompts/
│   │   ├── orchestrator.py         # ORCHESTRATOR_SYSTEM_PROMPT
│   │   ├── repo_ingestion.py       # REPO_INGESTION_SYSTEM_PROMPT
│   │   ├── architecture_analyst.py # ARCHITECTURE_ANALYST_SYSTEM_PROMPT
│   │   ├── qa_agent.py             # QA_AGENT_SYSTEM_PROMPT
│   │   └── doc_generator.py        # DOC_GENERATOR_SYSTEM_PROMPT
│   └── .env                        # Local dev environment variables (gitignored)
│
├── devcompass_mcp/                 # Custom MCP server package
│   ├── __init__.py
│   ├── server.py                   # MCP server bootstrap, tool registration
│   ├── security.py                 # Path validation, blocklists, sanitization
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_tools.py           # read_file, read_directory_tree, search_codebase, get_file_metadata
│   │   ├── git_tools.py            # get_git_log, get_recent_changes, get_contributors, get_commit_diff
│   │   ├── analysis_tools.py       # detect_stack, find_entry_points, count_lines_of_code, clone_repository
│   │   └── constants.py            # BLOCKED_PATTERNS, STACK_MANIFEST_FILES, ENTRY_POINT_PATTERNS
│   └── tests/
│       ├── test_file_tools.py
│       ├── test_git_tools.py
│       ├── test_analysis_tools.py
│       └── test_security.py
│
├── ui/
│   ├── __init__.py
│   ├── gradio_app.py               # Gradio UI definition
│   ├── runner.py                   # ADK session management for UI calls
│   └── static/
│       └── mermaid.min.js          # Bundled Mermaid.js for diagram rendering
│
├── tests/
│   ├── eval/
│   │   ├── eval_config.yaml        # ADK eval criteria and thresholds
│   │   └── datasets/
│   │       ├── qa_eval.json        # Q&A evaluation dataset
│   │       └── architecture_eval.json  # Architecture analysis evaluation dataset
│   ├── integration/
│   │   ├── test_full_pipeline.py   # End-to-end test with a small test repo
│   │   └── fixtures/
│   │       └── sample_repo/        # Minimal test repository for integration tests
│   └── unit/
│       ├── test_orchestrator.py
│       └── test_schemas.py
│
├── Dockerfile                      # Production container definition
├── docker-compose.yml              # Local development with all services
├── .dockerignore
├── pyproject.toml                  # Python project config and dependencies
├── .gitignore                      # Excludes .env, /tmp, __pycache__, etc.
├── README.md                       # DevCompass own documentation
└── ARCHITECTURE.md                 # DevCompass's own architecture doc (meta)
```

### Key File Explanations

| File | Purpose |
|---|---|
| `app/agent.py` | Must export `root_agent` — this is the ADK entrypoint. The file is discovered by `adk` CLI. |
| `app/agents/*.py` | Factory functions for each agent. Factories prevent the "agent already has a parent" error when building the agent tree. |
| `app/schemas/*.py` | Pydantic models for agent I/O. Centralized here to be imported by both agents and tests. |
| `app/prompts/*.py` | System prompts stored as module-level string constants. Separating prompts from agent definitions makes iteration faster and diffs cleaner. |
| `devcompass_mcp/server.py` | The MCP server entry point. Run via `python -m devcompass_mcp.server`. |
| `devcompass_mcp/security.py` | All path validation and file filtering logic. Isolated for focused unit testing. |
| `ui/runner.py` | Bridges Gradio (sync) with ADK (async). Creates sessions, runs agents, and streams progress back to the UI. |
| `tests/eval/datasets/*.json` | ADK evaluation datasets. Each entry has `input`, `expected_output`, and `reference_answer` for the eval framework. |
| `tests/integration/fixtures/sample_repo/` | A minimal 10-file Python FastAPI project used as the integration test target. Small enough to run in CI. |

---

## 10. Deployment Architecture

### 10.1 Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

# Copy application code
COPY app/ ./app/
COPY devcompass_mcp/ ./devcompass_mcp/
COPY ui/ ./ui/

# Create working directory for cloned repos
RUN mkdir -p /tmp/devcompass && chmod 777 /tmp/devcompass

# Expose Gradio port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD curl -f http://localhost:8080/ || exit 1

# Start Gradio UI (which internally starts the MCP server as a subprocess)
CMD ["python", "-m", "ui.gradio_app", "--server-port", "8080", "--server-name", "0.0.0.0"]
```

### 10.2 docker-compose.yml (local dev)

```yaml
version: "3.9"
services:
  devcompass:
    build: .
    ports:
      - "8080:8080"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GOOGLE_GENAI_USE_VERTEXAI=False
      - LOG_LEVEL=DEBUG
    volumes:
      - /tmp/devcompass:/tmp/devcompass
      - ./app:/app/app      # hot reload for dev
      - ./devcompass_mcp:/app/devcompass_mcp
    restart: unless-stopped
```

### 10.3 MCP Server in Container

The MCP server does not run as a separate container. It is started by ADK's `McpToolset` as a subprocess within the same container when agents need tools. The `StdioConnectionParams` configuration handles lifecycle:

```
Container Process Tree:
├── python -m ui.gradio_app       (main process, PID 1)
│   └── ADK Runner
│       └── McpToolset
│           └── python -m devcompass_mcp.server   (subprocess, started on demand)
```

### 10.4 Cloud Run Deployment

```bash
# Step 1: Build and push container
gcloud builds submit \
    --tag gcr.io/${GOOGLE_CLOUD_PROJECT}/devcompass:latest \
    .

# Step 2: Create secrets in Secret Manager
echo -n "${GOOGLE_API_KEY}" | \
    gcloud secrets create devcompass-google-api-key --data-file=-

# Step 3: Deploy to Cloud Run
gcloud run deploy devcompass \
    --image gcr.io/${GOOGLE_CLOUD_PROJECT}/devcompass:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 4Gi \
    --cpu 2 \
    --timeout 900 \
    --max-instances 3 \
    --set-secrets "GOOGLE_API_KEY=devcompass-google-api-key:latest" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=True"
```

### 10.5 Resource Requirements

| Resource | Value | Reason |
|---|---|---|
| Memory | 4 GiB | Repository clones and file content held in memory during analysis |
| CPU | 2 vCPU | Parallel MCP tool calls from multiple agents |
| Timeout | 900s | Full pipeline (ingest + architect + docs) can take 3-8 minutes |
| Max instances | 3 | Avoid API rate limits on Gemini; each instance makes concurrent requests |

### 10.6 Vertex AI vs AI Studio

| Environment | Config | Notes |
|---|---|---|
| Local dev | `GOOGLE_GENAI_USE_VERTEXAI=False`, `GOOGLE_API_KEY=...` | AI Studio free tier; quickest to set up |
| Cloud Run (competition) | `GOOGLE_GENAI_USE_VERTEXAI=True`, `GOOGLE_CLOUD_PROJECT=...` | Production-grade; auto-auth via service account |

---

## 11. Kaggle Evaluation Mapping

### 11.1 Key Concepts Demonstrated (≥ 3 required)

| Concept | Where Implemented | Score Impact |
|---|---|---|
| **ADK Multi-Agent System** | 5 agents (1 orchestrator + 4 specialists) with `mode="task"` delegation, shared session state, typed I/O schemas | Technical Implementation (50 pts) |
| **MCP Server** | Custom `devcompass-mcp-server` with 12 tools across 3 categories; security-enforced read-only access | Technical Implementation (50 pts) |
| **Antigravity** | Google's Antigravity vibe coding tool used to generate the DevCompass codebase from this specification; demonstrated in the video by showing the spec-to-code workflow | Video (30 pts) |
| **Security Features** | Path traversal prevention, secret file filtering, no code execution, API keys via environment, input validation | Technical Implementation (50 pts) |
| **Deployability** | Full Cloud Run deployment with Dockerfile, Secret Manager, health check, auto-auth | Technical Implementation (50 pts) |
| **Agent Skills CLI** | ADK agents structured as proper ADK project (`agents-cli`-compatible layout, `root_agent` export, eval datasets) | Technical Implementation (50 pts) |

This implements **all 6 key concepts**, providing maximum coverage.

### 11.2 Evaluation Criteria Mapping

#### Technical Implementation (50 points)

| Sub-criterion | DevCompass Implementation |
|---|---|
| Agent orchestration | `Orchestrator Agent` using ADK `Agent` with 4 `mode="task"` sub-agents; typed Pydantic I/O schemas; session state shared via `output_key` |
| Tool use | MCP server with 12 tools; each agent uses `McpToolset` with `tool_filter` for principle of least privilege |
| Multi-step reasoning | Full pipeline: ingestion → architecture analysis → Q&A/review → documentation — each step depends on the prior |
| State management | ADK session state with structured keys; `{state_key}` injection in agent instructions; progress tracking |
| Error handling | Sub-agent failure captured by orchestrator; progress log updated with error message; user prompted for action |

#### Documentation (20 points)

| Sub-criterion | DevCompass Implementation |
|---|---|
| README clarity | This spec → comprehensive README.md; includes quick start, architecture overview, config reference |
| Code documentation | All MCP tool functions have complete docstrings with input/output schema descriptions |
| Architecture diagram | ARCHITECTURE.md includes Mermaid diagram of agent topology and data flow |
| Evaluation datasets | `tests/eval/datasets/` with Q&A and architecture eval JSON for ADK eval framework |

#### Pitch / Video / Writeup (30 points)

| Sub-criterion | DevCompass Implementation |
|---|---|
| Problem clarity | Clear business problem (1-3 week onboarding tax); quantified pain; specific target users |
| Solution fit | Multi-agent approach directly maps to the problem's multi-step nature (ingest, analyze, answer, document) |
| Demo quality | See Section 13 — scripted 5-minute demo with three distinct use cases |
| Business value | Onboarding cost reduction calculable: if a developer costs $150K/year, 2 weeks of productivity = $5.7K per hire |

### 11.3 Business Track Alignment

The "Agents for Business" track requires demonstrating measurable business value. DevCompass targets the specific metric of **developer onboarding time** — a cost center that every engineering organization tracks:

- Average engineer fully loaded cost: $150,000-$300,000/year
- Onboarding non-productivity: 2-6 weeks
- At 50 engineers/year at $200K: **$385K-$1.15M in annual onboarding productivity loss**
- DevCompass target: compress the "understanding" phase from 2 weeks to 2 hours

---

## 12. 6-Day Implementation Plan

### Day 1 (July 1) — Foundation

**Goal:** Running MCP server with all tools; ADK project scaffold; basic CI.

**Morning (4h):**
- [ ] Run `agents-cli scaffold create devcompass` to initialize the ADK project structure
- [ ] Set up `pyproject.toml` with all dependencies
- [ ] Configure `.env` with `GOOGLE_API_KEY`
- [ ] Verify `adk web` launches the scaffold successfully

**Afternoon (4h):**
- [ ] Implement `devcompass_mcp/security.py`: `validate_path`, `is_blocked`, `validate_url`
- [ ] Implement `devcompass_mcp/tools/file_tools.py`: `read_file`, `read_directory_tree`, `get_file_metadata`
- [ ] Write `tests/unit/test_security.py` and `test_file_tools.py`
- [ ] Verify MCP server starts and tools respond: `python -m devcompass_mcp.server`

**Evening (2h):**
- [ ] Implement `devcompass_mcp/tools/git_tools.py`: all 4 git tools
- [ ] Smoke test against a real local repository

**Milestone:** MCP server runs; `read_file`, `read_directory_tree`, `search_codebase`, all git tools working.

---

### Day 2 (July 2) — Ingestion + Architecture Agents

**Goal:** First two specialist agents working end-to-end.

**Morning (4h):**
- [ ] Implement `devcompass_mcp/tools/analysis_tools.py`: `detect_stack`, `find_entry_points`, `count_lines_of_code`, `clone_repository`
- [ ] Define Pydantic schemas in `app/schemas/ingestion.py`
- [ ] Write `REPO_INGESTION_SYSTEM_PROMPT` in `app/prompts/repo_ingestion.py`
- [ ] Implement `create_repo_ingestion_agent()` in `app/agents/repo_ingestion.py`

**Afternoon (4h):**
- [ ] Test Repo Ingestion Agent against 2-3 real repos (a small Python project, a Node.js project)
- [ ] Iterate on the system prompt until output reliably matches `RepoIngestionOutput` schema
- [ ] Define Pydantic schemas in `app/schemas/architecture.py`
- [ ] Write `ARCHITECTURE_ANALYST_SYSTEM_PROMPT`
- [ ] Implement `create_architecture_analyst_agent()`

**Evening (2h):**
- [ ] Test Architecture Analyst Agent using Repo Ingestion output as input
- [ ] Validate Mermaid output renders correctly in a browser (use mermaid.live)
- [ ] Fix any schema validation errors

**Milestone:** Given a GitHub URL, agents produce a file tree, detected stack, and Mermaid architecture diagram.

---

### Day 3 (July 3) — Q&A + Documentation Agents + Orchestrator

**Goal:** Full 5-agent pipeline running end-to-end.

**Morning (4h):**
- [ ] Define schemas in `app/schemas/qa.py`
- [ ] Write `QA_AGENT_SYSTEM_PROMPT`
- [ ] Implement `create_qa_agent()`
- [ ] Test Q&A Agent with questions like "Where is the database connection configured?" against a test repo

**Afternoon (4h):**
- [ ] Define schemas in `app/schemas/docs.py`
- [ ] Write `DOC_GENERATOR_SYSTEM_PROMPT` with `{state_key}` injections
- [ ] Implement `create_documentation_generator_agent()`
- [ ] Wire all agents together in `app/agent.py` via `build_root_agent()`
- [ ] Write `ORCHESTRATOR_SYSTEM_PROMPT` and `create_orchestrator_agent()`

**Evening (2h):**
- [ ] Run full pipeline end-to-end: provide GitHub URL, request all artifacts
- [ ] Fix agent-to-agent state passing issues
- [ ] Verify generated README is usable quality

**Milestone:** All 5 agents run sequentially; README, ARCHITECTURE.md, and onboarding checklist generated.

---

### Day 4 (July 4) — Gradio UI + Integration Testing

**Goal:** Working web interface; Q&A chat loop; end-to-end tested on 3 different repositories.

**Morning (4h):**
- [ ] Implement `ui/runner.py`: async ADK session management, progress streaming
- [ ] Implement `ui/gradio_app.py`: full 4-tab layout
- [ ] Wire up analyze button → full pipeline → populate tabs
- [ ] Implement Q&A chat using `gr.ChatInterface`

**Afternoon (4h):**
- [ ] Test against 3 repositories: small Python FastAPI, medium Node.js Express, large Go project
- [ ] Fix UI issues: progress display, tab switching, download buttons
- [ ] Implement Mermaid diagram rendering in `gr.Markdown`
- [ ] Write `tests/integration/test_full_pipeline.py`

**Evening (2h):**
- [ ] Build Docker image and test locally: `docker compose up`
- [ ] Fix any containerization issues (git not found, temp directory permissions)
- [ ] Create `tests/integration/fixtures/sample_repo/` for CI

**Milestone:** Full working application running in Docker. All 4 tabs populated. Q&A chat functional.

---

### Day 5 (July 5) — Deployment + Video

**Goal:** Live Cloud Run deployment; recorded YouTube demo.

**Morning (3h):**
- [ ] Create GCP project (or use existing)
- [ ] Enable APIs: Cloud Run, Secret Manager, Artifact Registry
- [ ] Build and push container: `gcloud builds submit`
- [ ] Deploy to Cloud Run
- [ ] Verify public URL works; test all features on live deployment

**Afternoon (3h):**
- [ ] Run demo against a well-known open-source project (e.g., `fastapi/fastapi`, `pallets/flask`)
- [ ] Record 5-minute YouTube video following Section 13 demo script
- [ ] Upload to YouTube (unlisted)

**Evening (2h):**
- [ ] Create ADK eval datasets (`tests/eval/datasets/`)
- [ ] Run `adk eval` to verify quality metrics
- [ ] Polish any UI rough edges found during recording

**Milestone:** Live demo URL, YouTube video uploaded, eval passing.

---

### Day 6 (July 6) — Kaggle Writeup + Polish

**Goal:** Kaggle submission ready before deadline.

**Morning (3h):**
- [ ] Write Kaggle notebook writeup (problem → solution → demo → results)
- [ ] Add architecture diagram to writeup
- [ ] Write README.md for the submission repository

**Afternoon (3h):**
- [ ] Final README.md and ARCHITECTURE.md polish
- [ ] Verify all environment variable documentation is complete
- [ ] Add sample output screenshots to README

**Evening (2h):**
- [ ] Submit to Kaggle competition
- [ ] Final check: YouTube link, Cloud Run URL, GitHub repo all working
- [ ] Submit before 11:59 PM deadline

---

## 13. Demo Script

**Video length:** 5 minutes
**Target repository for demo:** `pallets/flask` (well-known, medium size, Python, good architecture)

---

### [0:00–0:30] Hook & Problem Statement

**Show:** A blank GitHub repository page for a complex open-source project. No README visible, just a wall of files.

**Script:**
> "You just joined a new team. You've been handed this codebase. You have a meeting in 30 minutes where you're expected to answer questions about it. This is the developer onboarding nightmare — and it's universal."

---

### [0:30–1:00] Introduce DevCompass

**Show:** The DevCompass Gradio UI opening in a browser. Clean, minimal interface.

**Script:**
> "DevCompass is a multi-agent AI system built on Google ADK that ingests any codebase and gives you a complete picture in minutes, not weeks. Let me show you what it does."

---

### [1:00–1:30] How DevCompass Was Built — Antigravity

**Show:** Split screen: `devcompass-spec.md` on the left, Antigravity interface on the right.

**Script:**
> "DevCompass itself was built using Antigravity — Google's vibe coding tool. We wrote a detailed technical specification: agent architecture, MCP server design, security constraints, deployment config. We fed that spec into Antigravity, and it generated the full codebase. This is vibe coding in practice — human judgment on the design, AI execution on the implementation."

**Show:** Briefly scroll through the spec in the editor, then show Antigravity accepting it and generating the project file tree.

> "The spec is in the GitHub repository if you want to see exactly what we gave it."

---

### [1:30–3:00] Full Pipeline Demo

**Show:** Type `https://github.com/pallets/flask` into the repository input. Click Analyze.

**Narrate as agents run:**

> [Progress indicator appears] "The Repo Ingestion Agent is cloning the repository and building an index. It's identified Python as the primary language, Flask as the framework — and found 47 Python files across 8 modules."

> [Progress updates] "The Architecture Analyst Agent is now reading the entry points and tracing the request flow. It's identifying three layers: the routing layer, the context management system, and the templating engine."

**Show:** Architecture tab populates with the Mermaid diagram.

> "Here's the architecture — a live diagram generated by analyzing the actual code. This took 90 seconds. Normally this would take a new developer 2-3 days to understand."

---

### [3:00–3:45] Documentation Tab

**Show:** Switch to Generated Docs tab. Show the README preview.

**Script:**
> "DevCompass didn't just describe the architecture — it generated a complete README, an ARCHITECTURE.md, and an API reference. All from reading the source code."

**Show:** Click the Architecture Overview sub-tab. Scroll through it.

> "The architecture doc includes the Mermaid diagram, a module responsibility table, identified design patterns — Flask uses the Application Factory pattern and the Request Context pattern — and a list of architectural concerns for a new developer."

**Show:** Click Download button for README.md.

> "Every artifact is downloadable. Teams can commit these directly to their repositories."

---

### [3:45–4:20] Q&A Chat Demo

**Show:** Switch to Q&A Chat tab.

**Type:** "How does Flask handle database connections across requests?"

**Show:** Answer appears with file references and code snippets highlighted.

**Script:**
> "Now I can ask natural language questions. The Q&A Agent reads the indexed codebase and gives precise answers with file and line references — not hallucinations."

**Type:** "Where is the application context defined and what does it manage?"

**Show:** Answer appears quickly.

> "Every answer cites its sources. You can follow the references to verify."

---

### [4:20–4:45] Onboarding Checklist

**Show:** Switch to Onboarding Checklist tab. Select "Backend" role.

**Script:**
> "Finally, the personalized onboarding checklist. For a backend developer joining this project, DevCompass has generated a step-by-step guide: what to read first, what to run, where the key extension points are."

**Show:** Scroll through the checklist. Show Day 1 through Week 1 sections.

> "This is what two weeks of painful self-discovery, compressed into a two-minute read."

---

### [4:45–5:00] Wrap

**Show:** Cloud Run URL in browser. Show the live deployment.

**Script:**
> "DevCompass is deployed on Google Cloud Run, built with Google ADK, and runs a custom MCP server for secure read-only codebase access. The repository, documentation, and live demo link are in the Kaggle submission. DevCompass — your compass for any codebase."

---

*End of specification.*

---

**Document version:** 1.0
**Competition:** AI Agents: Intensive Vibe Coding Capstone Project by Google on Kaggle
**Last updated:** July 1, 2026
