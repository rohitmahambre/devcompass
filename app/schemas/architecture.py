from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class ArchitectureAnalystInput(BaseModel):
    repo_path: str
    file_tree: str
    detected_stack: dict
    entry_points: List[str]
    specific_question: Optional[str] = Field(
        None,
        description="Optional: a specific architectural question to focus on"
    )

class ArchitectureAnalystOutput(BaseModel):
    architecture_summary: str = Field(
        description="2-3 paragraph narrative description of the architecture"
    )
    layers: List[dict] = Field(
        description="List of identified layers, each with name, description, and files"
    )
    module_responsibilities: List[dict] = Field(
        description="Each module/package with its responsibility and key files"
    )
    data_flow: str = Field(
        description="Description of how data flows through the system"
    )
    mermaid_diagram: str = Field(
        description="Valid Mermaid graph TD diagram of the architecture"
    )
    design_patterns: List[str] = Field(
        description="Identified design patterns (e.g. Repository, Factory, Observer)"
    )
    potential_concerns: List[str] = Field(
        description="Architectural concerns worth noting for a new developer"
    )
