from pydantic import BaseModel, Field
from typing import Optional, List

class DocGeneratorInput(BaseModel):
    requested_artifacts: List[str] = Field(
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

class DocGeneratorOutput(BaseModel):
    readme_content: Optional[str] = Field(None, description="Generated README.md in markdown")
    architecture_doc_content: Optional[str] = Field(None, description="Generated ARCHITECTURE.md in markdown")
    api_docs_content: Optional[str] = Field(None, description="Generated API reference in markdown")
    onboarding_checklist_content: Optional[str] = Field(None, description="Personalized onboarding checklist in markdown")
    artifacts_generated: List[str] = Field(description="Names of artifacts successfully generated")
