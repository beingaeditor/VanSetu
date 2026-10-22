"""
Prune AI Gateway Service — Explainable Ranking via Google Gemini.

Architecture:
- Connects to the Prune AI Gateway (https://api.withprune.com/v1) using OpenAI-compatible endpoints.
- Account: niharika1912singh@gmail.com (Google Gemini provider configured in Prune Vault).
- The PRUNE_API_KEY remains strictly on the backend and is never exposed to the client or frontend.
- Authoritative Ranking Invariant:
  The deterministic backend formula remains the authoritative source of corridor rankings.
  Gemini is used solely to generate an evidence-grounded textual explanation of why a corridor
  achieved its specific score given its spatial metrics and active weighting.
  Gemini does NOT recalculate, fabricate, or modify the official ranking.
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


def generate_deterministic_explanation(corridor_data: Dict[str, Any]) -> str:
    """
    Fallback deterministic explanation generated when AI gateway is not configured or offline.
    Ensures urban planners always receive transparent rationale without external dependencies.
    """
    name = corridor_data.get("name", "Unnamed Corridor")
    signals = corridor_data.get("signals") or {}

    # Check if this is a What-if Corridor Ranking explanation request
    heat_weight = corridor_data.get("heat_weight")
    if heat_weight is not None:
        hw = float(heat_weight)
        gdw = round(1.0 - hw, 4)
        heat = float(corridor_data.get("heat") if corridor_data.get("heat") is not None else signals.get("heat", 0.5))
        ndvi = float(corridor_data.get("ndvi") if corridor_data.get("ndvi") is not None else (1.0 - signals.get("green_deficit", 0.5)))
        green_def = round(1.0 - ndvi, 4)
        score = float(corridor_data.get("score") if corridor_data.get("score") is not None else corridor_data.get("priority_score", hw * heat + gdw * green_def))
        h_contrib = round(hw * heat, 4)
        g_contrib = round(gdw * green_def, 4)
        rank = corridor_data.get("rank")
        base_rank = corridor_data.get("baseline_rank")
        rank_change = corridor_data.get("rank_change")

        shift_clause = ""
        if rank is not None and base_rank is not None:
            if rank_change and rank_change > 0:
                shift_clause = f" Relative to the 0.60 baseline (Rank #{base_rank}), this corridor gained +{rank_change} place(s) to reach Rank #{rank}."
            elif rank_change and rank_change < 0:
                shift_clause = f" Relative to the 0.60 baseline (Rank #{base_rank}), this corridor moved {rank_change} place(s) to Rank #{rank}."
            else:
                shift_clause = f" It retains Rank #{rank} across both the 0.60 baseline and the current weighting."

        dominant = (
            f"thermal exposure ({h_contrib:.4f} from {hw:.2f} × Heat {heat:.4f})"
            if h_contrib >= g_contrib
            else f"vegetation scarcity ({g_contrib:.4f} from {gdw:.2f} × (1 - NDVI) {green_def:.4f})"
        )
        return (
            f"{name} achieves a deterministic What-if score of {score:.4f} using "
            f"score = {hw:.2f} × Heat ({heat:.4f}) + {gdw:.2f} × (1 - NDVI ({ndvi:.4f})) = {h_contrib:.4f} + {g_contrib:.4f} = {score:.4f}. "
            f"The primary contributor under the selected weight is {dominant}.{shift_clause}"
        )

    score = corridor_data.get("priority_score", 0.5)
    scenario = corridor_data.get("scenario", "balanced")
    heat = signals.get("heat", 0.5)
    green_def = signals.get("green_deficit", 0.5)
    aqi = signals.get("pollution", 0.5)
    ped = signals.get("pedestrian", 0.5)
    vuln = signals.get("vulnerable_pop", 0.5)

    lead_hazard = "thermal radiation exposure" if heat >= max(green_def, aqi) else (
        "airborne particulate pollution" if aqi >= max(heat, green_def) else "canopy and green infrastructure deficit"
    )

    return (
        f"{name} has been evaluated with an authoritative priority score of {score:.3f} under the '{scenario}' policy scenario. "
        f"The primary driver of need along this corridor is {lead_hazard} (normalized heat: {heat:.2f}, vegetation deficit: {green_def:.2f}, AQI stress: {aqi:.2f}). "
        f"Pedestrian footfall activity ({ped:.2f}) and socio-spatial vulnerability ({vuln:.2f}) further elevate the urgency for shaded, walkable green infrastructure."
    )


async def explain_corridor_ranking(corridor_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Request an AI explanation for a corridor's existing deterministic priority ranking
    through the Prune AI Gateway backed by Google Gemini.
    """
    settings = get_settings()
    api_key = os.environ.get("PRUNE_API_KEY") or settings.prune_api_key

    # Check if Prune API key is configured
    if not api_key or api_key in ("prune_your_key_here", ""):
        return {
            "status": "not_configured",
            "message": (
                "PRUNE_API_KEY is not configured on the backend. "
                "To enable Gemini-powered explanations via Prune, vault your Gemini API key in the Prune dashboard "
                "at https://app.withprune.com (Connect > Providers) and set PRUNE_API_KEY in the backend environment."
            ),
            "explanation": None,
            "fallback_explanation": generate_deterministic_explanation(corridor_data),
            "prune_metadata": None,
            "model_used": None,
        }

    # Prepare grounded prompt
    name = corridor_data.get("name", "Unnamed Corridor")
    district = corridor_data.get("district", "NCT of Delhi")
    highway = corridor_data.get("highway", "secondary")
    score = corridor_data.get("score") if corridor_data.get("score") is not None else corridor_data.get("priority_score", 0.5)
    feasibility = corridor_data.get("feasibility", 0.6)
    confidence = corridor_data.get("confidence", 0.7)
    scenario = corridor_data.get("scenario", "balanced")
    signals = corridor_data.get("signals") or {}
    weights = corridor_data.get("active_weights") or {}
    heat_weight = corridor_data.get("heat_weight")
    heat_val = corridor_data.get("heat") if corridor_data.get("heat") is not None else signals.get("heat", "N/A")
    ndvi_val = corridor_data.get("ndvi") if corridor_data.get("ndvi") is not None else "N/A"
    green_def_val = corridor_data.get("green_deficit") if corridor_data.get("green_deficit") is not None else signals.get("green_deficit", "N/A")
    rank = corridor_data.get("rank")
    baseline_rank = corridor_data.get("baseline_rank")
    rank_change = corridor_data.get("rank_change")
    baseline_score = corridor_data.get("baseline_score")

    what_if_block = ""
    if heat_weight is not None:
        gdw = round(1.0 - float(heat_weight), 4)
        what_if_block = f"""
What-if Corridor Ranking Parameters:
- Formula: score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)
- Selected heat_weight: {heat_weight}
- Complementary green-deficit weight (1 - heat_weight): {gdw}
- Normalized Heat: {heat_val}
- Normalized NDVI: {ndvi_val} (Green Deficit 1 - NDVI: {green_def_val})
- Heat Contribution: {corridor_data.get('heat_contribution', 'N/A')}
- Green-Deficit Contribution: {corridor_data.get('green_deficit_contribution', 'N/A')}
- Current Rank: #{rank} (Score: {score:.4f})
- Baseline (heat_weight=0.6) Rank: #{baseline_rank} (Baseline Score: {baseline_score})
- Rank Change from Baseline: {rank_change}
"""

    prompt_content = f"""You are an expert urban climate researcher and municipal GIS advisor reviewing VanSetu priority rankings.
Explain why the following corridor received its specific priority score based on the deterministic metrics below.

Corridor Details:
- Name: {name}
- District: {district}
- Road Hierarchy: {highway}
- Authoritative Priority Score: {score:.4f} (Scale: 0.0 to 1.0)
- Implementation Feasibility: {feasibility:.3f}
- Evidence Confidence: {confidence:.3f}
- Active Policy Scenario: {scenario}
{what_if_block}
Contributed Signals (0.0 = low stress, 1.0 = extreme stress):
- Land Surface Temperature / Heat Hazard: {heat_val}
- Canopy / Green Deficit (1 - NDVI): {green_def_val}
- Air Pollution / AQI Stress: {signals.get('pollution', 'N/A')}
- Pedestrian Activity Proxy: {signals.get('pedestrian', 'N/A')}
- Socio-spatial Vulnerability: {signals.get('vulnerable_pop', 'N/A')}

Active Normalized Policy Weights:
{json.dumps(weights, indent=2)}

Guidelines:
1. The priority score of {score:.4f} is authoritative and calculated by the backend mathematical model. Do NOT recalculate or contradict this score.
2. Provide a clear, professional explanation (2 brief paragraphs) suitable for municipal urban planners.
3. Highlight how the corridor's Heat value, NDVI value, and selected heat_weight (including any rank shift relative to the 0.6 baseline) drive this priority.
4. Conclude with why prioritizing this corridor aligns with climate resilience and pedestrian protection."""

    url = f"{settings.prune_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.prune_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are VanSetu's AI Climate Planning Analyst. You explain deterministic geospatial "
                    "corridor priority scores clearly and objectively without altering the mathematical results."
                ),
            },
            {"role": "user", "content": prompt_content},
        ],
        "temperature": 0.2,
        "max_tokens": 450,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "").strip()
                prune_meta = data.get("prune_metadata") or choice.get("prune_metadata")
                model_used = data.get("model", settings.prune_model)

                return {
                    "status": "success",
                    "explanation": content,
                    "prune_metadata": prune_meta,
                    "model_used": model_used,
                    "is_ai_generated": True,
                }
            elif response.status_code == 401:
                logger.warning("Prune API authentication failed (401). Invalid PRUNE_API_KEY.")
                return {
                    "status": "authentication_error",
                    "message": "Prune authentication failed. Please verify that your PRUNE_API_KEY is valid.",
                    "explanation": None,
                    "fallback_explanation": generate_deterministic_explanation(corridor_data),
                    "status_code": 401,
                }
            elif response.status_code == 429:
                logger.warning("Prune AI Gateway rate limit exceeded (429).")
                return {
                    "status": "rate_limited",
                    "message": "Prune rate limit reached. Returning deterministic explanation fallback.",
                    "explanation": None,
                    "fallback_explanation": generate_deterministic_explanation(corridor_data),
                    "status_code": 429,
                }
            else:
                logger.error(f"Prune API error HTTP {response.status_code}: {response.text}")
                return {
                    "status": "provider_error",
                    "message": f"Prune Gateway returned HTTP {response.status_code}.",
                    "explanation": None,
                    "fallback_explanation": generate_deterministic_explanation(corridor_data),
                    "status_code": response.status_code,
                }

    except httpx.TimeoutException:
        logger.warning("Prune API request timed out after 15s.")
        return {
            "status": "timeout",
            "message": "Prune AI Gateway request timed out. Using deterministic fallback.",
            "explanation": None,
            "fallback_explanation": generate_deterministic_explanation(corridor_data),
        }
    except Exception as e:
        logger.error(f"Unexpected error communicating with Prune AI Gateway: {str(e)}")
        return {
            "status": "error",
            "message": f"Connection error: {str(e)}",
            "explanation": None,
            "fallback_explanation": generate_deterministic_explanation(corridor_data),
        }
