from pydantic import BaseModel, Field
from typing import Optional, List, Dict

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

class QAAgentOutput(BaseModel):
    answer: str = Field(description="The answer to the user's question")
    referenced_files: List[dict] = Field(
        description="Files referenced, each with path and relevant line range"
    )
    code_snippets: List[dict] = Field(
        description="Relevant code snippets with file path and line numbers"
    )
    follow_up_suggestions: List[str] = Field(
        description="Suggested follow-up questions the user might want to ask"
    )
    review_findings: Optional[List[dict]] = Field(
        None,
        description="Code review findings with severity, category, file, line, description"
    )
