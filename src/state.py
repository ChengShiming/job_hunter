from typing import TypedDict, List, Optional, Any, Dict
from pydantic import BaseModel, Field

class JobRequirement(BaseModel):
    job_id: str = Field(..., description="The unique ID of the job listing.")
    title: str = Field(..., description="The title of the job.")
    location: str = Field(..., description="The location of the job.")
    link: str = Field(..., description="The direct URL to the job listing.")
    job_desc: str = Field(default="", description="A brief summary or description of the job.")
    job_requirements: str = Field(default="", description="Job requirements and qualifications.")

class GraphState(TypedDict):
    url: Optional[str]
    company_name: str
    recipe_config: Optional[Dict[str, Any]]
    scraped_data: List[JobRequirement]
    error: Optional[str]
    retry_count: int
    success: bool
    # We store the crawler in the state to reuse it
    crawler: Any 
