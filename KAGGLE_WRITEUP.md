# DevCompass: A Multi-Agent Codebase Intelligence System for Developer Onboarding

### Turning weeks of archaeology into hours of insight with Google ADK, custom MCP, and vibe-coded architecture

---

## Problem Statement

Every software team knows the ritual: a new developer joins, receives repository access, and then disappears for one to three weeks. They're not slacking — they're archaeologists, excavating layers of architectural decisions, tracing dependencies, decoding naming conventions, and trying to understand why the codebase is shaped the way it is. At $150,000 per year, two weeks of lost productivity costs $5,700 per hire before they write a single line of meaningful code.

The tools available today don't solve this. Static documentation goes stale the moment it's written. README files describe what a project does, not how it works or where to start. Senior engineers become unwilling tour guides, answering the same questions repeatedly across every new hire cycle. GitHub Copilot and similar tools help once a developer already knows the codebase — they don't help you understand it from scratch.

What doesn't exist is a tool that can autonomously traverse a real repository, reason across file boundaries, understand the architecture as a whole, and produce structured, role-specific onboarding deliverables on demand. DevCompass is that tool.

Given any GitHub URL or local path, DevCompass produces a Mermaid architecture diagram, a generated README, an ARCHITECTURE.md document, a role-specific onboarding checklist tailored to backend engineers, frontend engineers, or DevOps practitioners, and a Q&A interface that answers questions about the codebase with file and line citations. It compresses weeks of orientation into hours of guided exploration.

---

## Why Agents — Not a Single LLM Call

The obvious question is why this requires an agentic system at all. Why not send the codebase to a large context window model and ask it to produce everything at once?

The answer is that the task is genuinely multi-step, stateful, and heterogeneous in a way that breaks the single-call model. Cloning a repository, traversing its file tree, detecting the technology stack, analyzing architectural patterns, and producing multiple structured documents are not operations that happen in one inference pass — they require tool invocation, intermediate state, branching logic, and different cognitive modes for different subtasks.

Different subtasks also benefit from different models. File ingestion and Q&A are throughput problems: processing thousands of files and returning cited answers quickly. Architecture analysis and documentation writing are reasoning problems: synthesizing patterns across the codebase, making judgment calls about what matters, and writing prose that will be read by humans. Using Gemini 2.5 Flash for the former and Gemini 2.5 Pro for the latter is not an optimization afterthought — it's central to making the system both fast and high quality.

Finally, agents maintain shared session state. Each specialist agent builds on what the previous one discovered. The Documentation Generator agent doesn't re-analyze the codebase — it reads the structured findings produced by the Architecture Analyst and turns them into prose. This accumulation of understanding across the pipeline is what makes the output coherent rather than a collection of independent summaries.

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
│ flash-2.5  │  │  pro-2.5     │  │ flash-2.5│  │  pro-2.5       │
└────────────┘  └──────────────┘  └──────────┘  └────────────────┘
                        │
            ┌───────────────────────┐
            │  devcompass-mcp-server │
            │  12 read-only tools    │
            │  File / Git / Analysis │
            └───────────────────────┘
```

The Orchestrator Agent runs on Gemini 2.5 Pro and acts as the system's router and state manager. It receives the user's request, determines which sub-agents to invoke and in what order, and manages the shared session state that flows between agents. Critically, it can adapt the pipeline based on what the user actually asks for — if someone wants only Q&A without generating documentation, the orchestrator skips the Documentation Generator entirely.

The Repo Ingestion Agent, running on Gemini 2.5 Flash, handles the first contact with the codebase. It clones the repository (shallow clone, depth=1, for speed), traverses the file tree respecting .gitignore patterns, reads key configuration files, and produces a structured inventory of the repository's contents and technology stack.

The Architecture Analyst Agent, running on Gemini 2.5 Pro, receives the ingestion output and reasons about it. It calls MCP tools to examine entry points, analyze dependency graphs, and trace data flows. It produces a structured architectural assessment including a Mermaid diagram.

The Q&A Agent, running on Gemini 2.5 Flash, answers developer questions with citations. It uses context caching to avoid re-processing the repository on every question, and it cites specific files and line numbers so answers are verifiable.

The Documentation Generator Agent, running on Gemini 2.5 Pro, synthesizes everything into deliverables: README.md, ARCHITECTURE.md, and role-specific onboarding checklists. It reads from session state rather than re-analyzing the codebase, making it fast and consistent with the other agents' findings.

---

## Custom MCP Server: devcompass-mcp-server

The backbone of DevCompass's tool access is a custom MCP server built with FastMCP, exposing 12 read-only tools across three categories.

File tools include `read_file`, `read_directory_tree`, `search_codebase`, and `get_file_metadata`. These give agents structured access to repository contents without requiring arbitrary filesystem access. `read_directory_tree` respects .gitignore patterns via the pathspec library, so agents don't waste context on build artifacts and vendored dependencies.

Git tools include `get_git_log`, `get_recent_changes`, `get_contributors`, and `get_commit_diff`. These let the Architecture Analyst understand not just what the code looks like now but how it evolved — which files change together, who owns which areas, where recent activity is concentrated.

Analysis tools include `detect_stack`, `find_entry_points`, `count_lines_of_code`, and `clone_repository`. These encode domain logic that would otherwise have to be re-derived through inference — stack detection from dependency manifests, entry point identification from framework conventions, and repository cloning with the security constraints described below.

Security was not an afterthought. Path traversal prevention is implemented via `pathlib.Path.resolve()` combined with `is_relative_to()` to ensure every file access stays within the cloned repository boundary. A blocked file list prevents reading `.env`, `credentials.json`, `id_rsa`, `*.pem`, and any filename matching `*secret*` or `*password*`. The server executes no code — every tool is read-only. These constraints are enforced at the MCP server level, not in agent prompts, which means they cannot be bypassed by prompt injection or model hallucination.

---

## Key Design Decisions

Several engineering choices defined the character of the system.

**Least-privilege tool filtering.** Every agent receives only the MCP tools it needs. The Repo Ingestion Agent can clone and traverse but cannot search — it doesn't need to. The Q&A Agent can search and read files but cannot clone repositories. This is implemented via `tool_filter` on each agent definition, and it means a compromised or misbehaving agent cannot perform operations outside its role.

**Pydantic output schemas throughout.** Every agent produces a typed Pydantic model as output. This prevents hallucinated structure from propagating through the pipeline — if an agent produces output that doesn't match the schema, it fails loudly rather than silently passing malformed data downstream.

**`before_model_callback` for state management.** The Orchestrator uses a `before_model_callback` to unpack sub-agent results from the ADK event stream and write them into session state before each subsequent agent invocation. This gives the system a clean separation between the ADK event model (streaming, asynchronous) and the shared state model (structured, synchronous).

**Context caching for Q&A.** Repository files can easily fill hundreds of thousands of tokens. `ContextCacheConfig` with `min_tokens=4096` and a TTL of 3600 seconds ensures the repository context is cached for the duration of an onboarding session, reducing both latency and cost substantially.

**Shallow clones.** Depth-1 cloning brings ingestion time for most repositories under 30 seconds without sacrificing the structural analysis that matters for onboarding.

---

## Demo Walkthrough

A developer pastes the GitHub URL for a medium-sized production repository into the Gradio interface. The Orchestrator determines full onboarding mode is appropriate and invokes the Repo Ingestion Agent. Within 25 seconds, the repository is cloned and indexed — the UI shows the detected stack (Python, FastAPI, PostgreSQL, Docker) and file count.

The Architecture Analyst runs next, examining entry points, tracing the API layer through to the database models, and identifying the background job system. It produces a Mermaid diagram showing five major components and their relationships, along with a prose summary of the detected architectural patterns.

The Documentation Generator follows, producing a README, ARCHITECTURE.md, and three role-specific onboarding checklists. The entire pipeline completes in under two minutes.

The developer then switches to Q&A mode and asks: "Where does authentication happen and how does token validation work?" The Q&A Agent responds in eight seconds with a cited answer referencing specific files and line numbers, explaining the flow precisely.

---

## The Build Journey: Spec First, Vibe Second

DevCompass was built using Antigravity, Google's vibe coding tool. Rather than writing code directly, we began by authoring a comprehensive 2,257-line technical specification. This document covered the complete agent architecture with roles, models, and tool access for each agent; the full MCP tool schema with parameter types, return types, and error conditions; the security model with explicit threat scenarios and mitigations; all Pydantic schemas for inter-agent communication; the Gradio UI layout; the Docker deployment configuration; and the `agents-cli-manifest.yaml` for Agent Skills CLI registration.

Writing the spec took roughly a day. It forced decisions that would otherwise have been deferred to implementation time — particularly around security constraints and the session state model. We fed this specification into Antigravity, which generated the full codebase. The generated code required targeted fixes: a null check in the `before_model_callback`, async corrections in the Gradio event handlers, and path resolution adjustments in the MCP security module. These took under two hours to resolve.

This workflow has a deeper lesson. The spec document became the ground truth for the project. When a behavior was unclear, we went back to the spec, not the code. When a bug appeared, the spec told us what the intended behavior should have been. Vibe coding, done well, is not "AI writes the code and humans approve it" — it is "humans design the system rigorously, AI implements it, humans verify the implementation matches the design."

---

## Concepts Demonstrated

DevCompass demonstrates all six course concepts. The ADK multi-agent system is the core architecture: five agents with defined roles, typed I/O, and an orchestrator managing the pipeline. The custom MCP server exposes 12 tools with real security enforcement. Antigravity drove the implementation from a machine-readable specification. Security features are implemented at the infrastructure level — path traversal prevention, blocked file lists, read-only contracts, and least-privilege tool filtering. Deployability is covered by a Docker image and Cloud Run configuration. Agent Skills CLI integration includes an `agents-cli-manifest.yaml` and evaluation datasets covering the core onboarding scenarios.

---

## Conclusion

Developer onboarding is a solved problem in the sense that we know how it should work. It's an unsolved problem in the sense that it doesn't scale. DevCompass replaces the senior engineer tour guide with an agent system that knows the codebase as deeply as the git history and file structure allow, and communicates what it knows in the formats developers actually need.

The multi-agent architecture isn't a technical flourish — it reflects the genuine structure of the problem. The custom MCP server isn't boilerplate — it's the security boundary that makes the system safe to run against production repositories. The spec-first Antigravity workflow demonstrates that vibe coding works for systems with real architectural complexity, provided humans invest in the specification before handing off to AI.

Point it at a repository and get your new hire productive before lunch.

---

## Links

- **GitHub Repository:** https://github.com/rohitmahambre/devcompass
- **Track:** Agents for Business
