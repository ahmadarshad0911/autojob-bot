from typing import List, Optional
from pydantic import BaseModel, Field

class ContactInfo(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

class ExperienceItem(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = "Present"
    is_current: Optional[bool] = False
    highlights: List[str] = Field(default_factory=list)

class ProjectItem(BaseModel):
    name: str
    role: Optional[str] = None
    url: Optional[str] = None
    year: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)

class EducationItem(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None

class MasterProfile(BaseModel):
    detected_target_roles: List[str]
    suggested_experience_level: str
    contact: ContactInfo
    summary: str
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
