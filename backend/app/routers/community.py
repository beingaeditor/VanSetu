"""
Community & Health Data Router — Secondary User Input Endpoints

Handles structured data submissions from:
1. Community activity providers (vendors, schools, universities)
2. Environmental risk authorities (pollution boards, disaster management)
3. Health departments (heatstroke, dehydration, respiratory data)

Data is stored as JSON files in backend/data/feedback/.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

router = APIRouter()

# Storage directory
FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
COMMUNITY_FILE = FEEDBACK_DIR / "community_data.json"
HEALTH_FILE = FEEDBACK_DIR / "health_data.json"


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(filepath: Path) -> list:
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return []


def _save_json(filepath: Path, data: list):
    _ensure_dir()
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ─── Community Data Models ──────────────────────────────────

class CommunityDataSubmission(BaseModel):
    """Structured data from community activity providers and environmental authorities."""
    city: str = "Delhi"
    ward: str = ""
    street: str = ""
    userType: str = ""
    heatLevel: str = ""
    shadeLevel: str = ""
    pedestrianActivity: str = ""
    peakTime: str = ""
    pollutionLevel: str = ""
    pollutionSource: str = ""
    heatwaveRisk: str = ""
    vulnerablePopulation: str = ""
    emergencyHeatIncidents: str = ""


class CommunityDataResponse(BaseModel):
    id: str
    status: str
    message: str
    submitted_at: str


# ─── Health Data Models ─────────────────────────────────────

class HealthDataSubmission(BaseModel):
    """Structured data from health departments."""
    district: str
    area: str = ""
    heatstroke_cases: int = Field(default=0, ge=0)
    dehydration_cases: int = Field(default=0, ge=0)
    respiratory_cases: int = Field(default=0, ge=0)
    emergency_visits: int = Field(default=0, ge=0)
    vulnerable_population_pct: float = Field(default=0, ge=0, le=100)
    heat_risk_level: str = "Low"


class HealthDataResponse(BaseModel):
    id: str
    status: str
    message: str
    submitted_at: str


# ─── Endpoints ──────────────────────────────────────────────

@router.post(
    "/community-data",
    response_model=CommunityDataResponse,
    tags=["Community Data"],
    summary="Submit community/environmental observation data"
)
async def submit_community_data(
    body: CommunityDataSubmission,
    request: Request
) -> CommunityDataResponse:
    """
    Accept structured observations from secondary users.

    Community activity providers submit: heat exposure, shade,
    pedestrian activity, peak time data.

    Environmental risk authorities submit: pollution levels,
    heatwave risk, vulnerable population data.
    """
    submission_id = str(uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "id": submission_id,
        "submitted_at": now,
        "client_ip": request.client.host if request.client else "unknown",
        **body.model_dump()
    }

    # Append to file
    records = _load_json(COMMUNITY_FILE)
    records.append(record)
    _save_json(COMMUNITY_FILE, records)

    print(f"✅ Community data submitted: {submission_id} from {body.city}/{body.ward}")

    return CommunityDataResponse(
        id=submission_id,
        status="success",
        message=f"Community observation recorded for {body.city}, {body.ward}",
        submitted_at=now
    )


@router.get(
    "/community-data",
    tags=["Community Data"],
    summary="Get all community data submissions"
)
async def get_community_data() -> List[Dict[str, Any]]:
    """Return all community data submissions."""
    return _load_json(COMMUNITY_FILE)


@router.post(
    "/health-data",
    response_model=HealthDataResponse,
    tags=["Health Data"],
    summary="Submit health department data"
)
async def submit_health_data(
    body: HealthDataSubmission,
    request: Request
) -> HealthDataResponse:
    """
    Accept health department data for a specific location.

    Includes: heatstroke cases, dehydration, respiratory illness,
    emergency visits, vulnerable population %, heat risk level.
    """
    submission_id = str(uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "id": submission_id,
        "submitted_at": now,
        "client_ip": request.client.host if request.client else "unknown",
        **body.model_dump()
    }

    records = _load_json(HEALTH_FILE)
    records.append(record)
    _save_json(HEALTH_FILE, records)

    total_cases = body.heatstroke_cases + body.dehydration_cases + body.respiratory_cases
    print(f"✅ Health data submitted: {submission_id} — {body.district}/{body.area} ({total_cases} cases)")

    return HealthDataResponse(
        id=submission_id,
        status="success",
        message=f"Health data recorded for {body.district} ({total_cases} total cases)",
        submitted_at=now
    )


@router.get(
    "/health-data/{district}",
    tags=["Health Data"],
    summary="Get health data for a district"
)
async def get_health_data(district: str) -> List[Dict[str, Any]]:
    """Return health data submissions for a specific district."""
    all_records = _load_json(HEALTH_FILE)
    return [r for r in all_records if r.get("district", "").lower() == district.lower()]


@router.get(
    "/health-data",
    tags=["Health Data"],
    summary="Get all health data submissions"
)
async def get_all_health_data() -> List[Dict[str, Any]]:
    """Return all health data submissions."""
    return _load_json(HEALTH_FILE)
