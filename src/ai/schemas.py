from pydantic import BaseModel, Field
from typing import List, Optional


class AnamnesisInput(BaseModel):
    patient_name: str
    age: int
    main_complaint: str
    symptoms: List[str]
    current_medications: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    medical_history: Optional[str] = None


class ClinicalAnalysis(BaseModel):
    probable_conditions: List[str]
    risk_level: str
    recommended_exams: List[str]
    red_flags: List[str]


class TreatmentPlan(BaseModel):
    cannabinoid_ratio: str
    suggested_dosage: str
    administration_route: str
    monitoring_plan: str
    precautions: List[str]


class ScientificReport(BaseModel):
    summary: str
    supporting_evidence: List[str]
    references: List[str]
