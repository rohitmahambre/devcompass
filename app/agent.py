# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig

from .agents.orchestrator import create_orchestrator_agent
from .agents.repo_ingestion import create_repo_ingestion_agent
from .agents.architecture_analyst import create_architecture_analyst_agent
from .agents.qa_agent import create_qa_agent
from .agents.doc_generator import create_doc_generator_agent

# Initialize GCP project credentials from environment or defaults
try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    pass

os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

# Check if GOOGLE_API_KEY is defined in env (AI Studio key)
# If not, ADK will default to Vertex AI credentials.
if not os.environ.get("GOOGLE_API_KEY"):
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    else:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

def build_root_agent() -> Agent:
    # Factory functions are used for each sub-agent to prevent the "agent already
    # has a parent" error that occurs when the same Agent instance is reused across
    # multiple Runner or App instantiations (e.g., during hot-reload in dev).
    repo_ingestion = create_repo_ingestion_agent()
    architect = create_architecture_analyst_agent()
    qa = create_qa_agent()
    doc_gen = create_doc_generator_agent()

    orchestrator = create_orchestrator_agent(
        sub_agents=[repo_ingestion, architect, qa, doc_gen]
    )
    return orchestrator

root_agent = build_root_agent()

# ContextCacheConfig enables Gemini's implicit caching for large repo contexts.
# min_tokens=4096: only cache payloads large enough to benefit (avoids cache
# overhead on small messages). ttl_seconds=3600: context stays warm for 1 hour,
# covering a typical analysis session. cache_intervals=5: cache is checked every
# 5 turns so repeated Q&A questions about the same repo don't re-read all files.
app = App(
    name="app",
    root_agent=root_agent,
    context_cache_config=ContextCacheConfig(
        min_tokens=4096,
        ttl_seconds=3600,
        cache_intervals=5,
    ),
)
