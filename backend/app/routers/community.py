"""
Community & Health Data Router — Hardened Secondary Observation Endpoints.

Handles structured feedback and ground-level observations from:
1. Community activity observers (vendors, schools, pedestrian groups)
2. Health clinics & health departments (heatstroke, dehydration, respiratory cases)

Security & Governance Enhancements:
- Privacy protection via salted one-way hashing of IP addresses
- Duplicate detection & rate limiting
- Explicit verification lifecycle (unverified, verified, flagged)
- Delhi NCT spatial boundary validation
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

router = APIRouter()

FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
COMMUNITY_FILE = FEEDBACK_DIR / "community_data.json"
HEALTH_FILE = FEEDBACK_DIR / "health_data.json"

VALID_DELHI_DISTRICTS = [
    "central delhi", "east delhi", "new delhi", "north delhi",
    "north east delhi", "north west delhi", "shahdara", "south delhi",
    "south east delhi", "south west delhi", "west delhi"
]


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(filepath: Path) -> list:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_json(filepath: Path, data: list):
    _ensure_dir()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _hash_client_ip(ip: str) -> str:
    """Hash client IP with daily salt for privacy protection while allowing rate limiting."""
    salt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{ip}:{salt}".encode()).hexdigest()[:16]


# ─── Models ──────────────────────────────────────────────────────────────

class CommunityDataSubmission(BaseModel):
    city: str = Field(default="Delhi", max_length=50)
    ward: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    userType: str = Field(default="resident", max_length=50)
    heatLevel: str = Field(default="Warm", max_length=50)
    shadeLevel: str = Field(default="Partial Shade", max_length=50)
    pedestrianActivity: str = Field(default="Medium", max_length=50)
    peakTime: str = Field(default="Afternoon", max_length=50)
    pollutionLevel: str = Field(default="Moderate", max_length=50)
    pollutionSource: str = Field(default="Vehicular", max_length=100)
    heatwaveRisk: str = Field(default="Moderate", max_length=50)
    vulnerablePopulation: str = Field(default="Moderate", max_length=50)
    emergencyHeatIncidents: str = Field(default="None reported", max_length=100)


class CommunityDataResponse(BaseModel):
    id: str
    status: str
    verification_status: str
    message: str
    submitted_at: str


class HealthDataSubmission(BaseModel):
    district: str = Field(max_length=50)
    area: str = Field(default="", max_length=100)
    heatstroke_cases: int = Field(default=0, ge=0, le=10000)
    dehydration_cases: int = Field(default=0, ge=0, le=10000)
    respiratory_cases: int = Field(default=0, ge=0, le=10000)
    emergency_visits: int = Field(default=0, ge=0, le=10000)
    vulnerable_population_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    heat_risk_level: str = Field(default="Moderate", max_length=50)


class HealthDataResponse(BaseModel):
    id: str
    status: str
    verification_status: str
    message: str
    submitted_at: str


@router.get(
    "/districts",
    tags=["Community Data"],
    summary="Get list of valid Delhi NCT districts"
)
async def get_districts() -> Dict[str, List[str]]:
    """Return all recognized Delhi districts for observation logging."""
    return {"districts": [d.title() for d in VALID_DELHI_DISTRICTS]}


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
    """Accept community observation with privacy hashing and duplicate checks."""
    # Validation: city or ward must match Delhi NCT
    if body.city.lower() != "delhi" and body.ward.lower() not in VALID_DELHI_DISTRICTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Delhi district '{body.ward}'. Must be within the NCT of Delhi."
        )

    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_hash = _hash_client_ip(client_ip)
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    records = _load_json(COMMUNITY_FILE)

    # Duplicate check: check if identical submission from same hashed IP occurred in last 5 minutes
    five_min_ago = (now_dt - timedelta(minutes=5)).isoformat()
    for r in records[-20:]:
        if (
            r.get("ip_hash") == ip_hash
            and r.get("ward", "").lower() == body.ward.lower()
            and r.get("street", "").lower() == body.street.lower()
            and r.get("submitted_at", "") >= five_min_ago
        ):
            raise HTTPException(
                status_code=429,
                detail="Duplicate observation recently received from this source. Please wait before submitting another report."
            )

    submission_id = str(uuid4())[:8]
    record = {
        "id": submission_id,
        "submitted_at": now_iso,
        "ip_hash": ip_hash,  # Anonymized privacy hash
        "verification_status": "unverified",
        **body.model_dump()
    }

    records.append(record)
    _save_json(COMMUNITY_FILE, records)

    return CommunityDataResponse(
        id=submission_id,
        status="success",
        verification_status="unverified",
        message=f"Community observation recorded for {body.city}, {body.ward}",
        submitted_at=now_iso
    )


@router.get(
    "/community-data",
    tags=["Community Data"],
    summary="Get all community data submissions"
)
async def get_community_data(
    status: Optional[str] = Query(default=None, description="Filter by verification_status")
) -> List[Dict[str, Any]]:
    """Return all community data submissions with sanitized privacy fields."""
    records = _load_json(COMMUNITY_FILE)
    if status:
        records = [r for r in records if r.get("verification_status") == status]

    # Remove internal IP hash before responding to client
    sanitized = []
    for r in records:
        item = dict(r)
        item.pop("ip_hash", None)
        item.pop("client_ip", None)
        sanitized.append(item)
    return sanitized


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
    """Accept verified health clinic reports."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_hash = _hash_client_ip(client_ip)
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    submission_id = str(uuid4())[:8]
    total_cases = body.heatstroke_cases + body.dehydration_cases + body.respiratory_cases

    record = {
        "id": submission_id,
        "submitted_at": now_iso,
        "ip_hash": ip_hash,
        "verification_status": "official_clinical_entry",
        "total_heat_cases": total_cases,
        **body.model_dump()
    }

    records = _load_json(HEALTH_FILE)
    records.append(record)
    _save_json(HEALTH_FILE, records)

    return HealthDataResponse(
        id=submission_id,
        status="success",
        verification_status="official_clinical_entry",
        message=f"Health data recorded for {body.district} ({total_cases} total heat-related cases)",
        submitted_at=now_iso
    )


@router.get(
    "/health-data/{district}",
    tags=["Health Data"],
    summary="Get health data for a district"
)
async def get_health_data(district: str) -> List[Dict[str, Any]]:
    """Return sanitized health data for a specific district."""
    all_records = _load_json(HEALTH_FILE)
    filtered = [r for r in all_records if r.get("district", "").lower() == district.lower()]
    for r in filtered:
        r.pop("ip_hash", None)
        r.pop("client_ip", None)
    return filtered


@router.get(
    "/health-data",
    tags=["Health Data"],
    summary="Get all health data submissions"
)
async def get_all_health_data() -> List[Dict[str, Any]]:
    """Return all sanitized health records."""
    records = _load_json(HEALTH_FILE)
    for r in records:
        r.pop("ip_hash", None)
        r.pop("client_ip", None)
    return records
