# api/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Any


# --- Input schema (what frontend sends) ---
class CandidateIn(BaseModel):
    JobTitle: str
    Mode: str
    Location: str
    Stipend: Optional[int] = None
    Duration: Optional[int] = None
    candidate_id: Optional[str] = None


# --- Output schema for one internship ---
class InternshipOut(BaseModel):
    id: Optional[Any] = None
    JobTitle: str
    CompanyName: str
    States: str
    JobType: str
    match_score: float


# --- Output schema for recommendation API ---
class RecommendOut(BaseModel):
    candidate: CandidateIn
    match_probability: float
    recommendations: List[InternshipOut]
