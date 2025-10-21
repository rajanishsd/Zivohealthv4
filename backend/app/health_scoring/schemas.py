from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SpecEnvelope(BaseModel):
    specVersion: str = Field(..., alias="specVersion")
    updated: str
    scoring: Dict[str, Any]
    modalities: Dict[str, Any]
    ageSexAdjustments: Dict[str, Any]
    explainability: Dict[str, Any]


class SpecCreate(BaseModel):
    version: str
    name: str
    spec_json: Dict[str, Any]
    is_default: bool = False


class SpecResponse(BaseModel):
    id: int
    version: str
    name: str
    is_default: bool
    spec_json: Dict[str, Any]


class ScoreResult(BaseModel):
    date: str
    chronic: float
    acute: float
    overall: float
    confidence: float
    detail: Dict[str, Any]
    spec_version: str


