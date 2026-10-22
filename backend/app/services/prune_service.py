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


# ──────────────────────────────────────────────────────────────────────────────
# Van Setu AI Action Agent (Structured Typed Actions + Grounded Reasoning)
# ──────────────────────────────────────────────────────────────────────────────

import re
from typing import List

SUPPORTED_SCENARIOS = {
    "heat_focused": {"label": "Heat-Focused", "heat_weight": 0.85},
    "green_focused": {"label": "Green-Focused", "heat_weight": 0.25},
    "balanced": {"label": "Balanced (Default)", "heat_weight": 0.60},
    "health_focused": {"label": "Health-Focused", "heat_weight": 0.70},
    "equity_focused": {"label": "Equity-Focused", "heat_weight": 0.55},
    "budget_conscious": {"label": "Budget-Conscious (Template)", "heat_weight": 0.60},
    "custom_pro": {"label": "Custom Professional Scenario", "heat_weight": 0.60},
}


def parse_deterministic_agent_actions(
    user_message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministic intent & spatial action parser for Van Setu AI Agent.
    Produces validated typed actions and a grounded response using real workspace context.
    """
    msg = (user_message or "").strip()
    msg_lower = msg.lower()
    actions: List[Dict[str, Any]] = []
    notes: List[str] = []

    current_hw = float(context.get("heat_weight", 0.6))
    current_mode = str(context.get("mode", "public"))
    current_scenario = str(context.get("scenario", "balanced"))
    selected_corridor = context.get("selected_corridor") or {}
    available_corridors = context.get("available_corridors") or []

    # 1. Detect explicit heat_weight change (e.g., "set heat weight to 0.85", "heat_weight=0.9", "weight 0.3")
    weight_match = re.search(
        r"(?:heat\s*weight|heat_weight|weight|w)\s*(?:to|=|of|at|:)?\s*([01](?:\.\d+)?|0?\.\d+)",
        msg_lower,
    )
    if weight_match:
        try:
            w_val = round(float(weight_match.group(1)), 2)
            if 0.0 <= w_val <= 1.0:
                actions.append({
                    "type": "SET_HEAT_WEIGHT",
                    "payload": {"heat_weight": w_val},
                    "label": f"Set Heat Weight to {w_val:.2f} (Green Deficit {(1.0 - w_val):.2f})",
                    "requires_confirmation": False,
                })
                current_hw = w_val
                notes.append(
                    f"Updated What-if `heat_weight` to **{w_val:.2f}** (complementary green-deficit weight **{1.0 - w_val:.2f}**)."
                )
        except ValueError:
            pass
    elif "reset" in msg_lower and ("weight" in msg_lower or "baseline" in msg_lower or "default" in msg_lower):
        actions.append({
            "type": "SET_HEAT_WEIGHT",
            "payload": {"heat_weight": 0.60},
            "label": "Reset Heat Weight to 0.60 (Baseline)",
            "requires_confirmation": False,
        })
        current_hw = 0.60
        notes.append("Reset `heat_weight` to the **0.60** baseline.")

    # 2. Detect scenario selection
    scenario_patterns = [
        ("heat_focused", ["heat-focused", "heat focused", "heat scenario", "thermal focus", "heat resilience"]),
        ("green_focused", ["green-focused", "green focused", "green scenario", "vegetation focus", "canopy focus", "ndvi focus"]),
        ("balanced", ["balanced scenario", "balanced preset", "default scenario"]),
        ("health_focused", ["health-focused", "health focused", "health scenario", "air quality scenario"]),
        ("equity_focused", ["equity-focused", "equity focused", "equity scenario", "vulnerable scenario", "pedestrian equity"]),
        ("budget_conscious", ["budget-conscious", "budget conscious", "budget scenario", "cost-conscious", "low budget"]),
        ("custom_pro", ["custom professional", "custom scenario", "custom weights"]),
    ]
    for sc_id, phrases in scenario_patterns:
        if any(p in msg_lower for p in phrases):
            sc_meta = SUPPORTED_SCENARIOS[sc_id]
            actions.append({
                "type": "SELECT_SCENARIO",
                "payload": {"scenario": sc_id, "heat_weight": sc_meta["heat_weight"]},
                "label": f"Activate {sc_meta['label']} Scenario",
                "requires_confirmation": False,
            })
            current_scenario = sc_id
            current_hw = sc_meta["heat_weight"]
            notes.append(f"Activated the **{sc_meta['label']}** scenario (`heat_weight = {current_hw:.2f}`).")
            break

    # 3. Detect Top N change ("top 10", "top 15", "top 5")
    top_match = re.search(r"\btop\s*(5|10|15)\b", msg_lower)
    if top_match:
        top_n_val = int(top_match.group(1))
        actions.append({
            "type": "SET_TOP_N",
            "payload": {"top": top_n_val},
            "label": f"Show Top {top_n_val} Ranked Corridors",
            "requires_confirmation": False,
        })
        notes.append(f"Updated ranking display to **Top {top_n_val}** corridors.")

    # 4. Detect mode switch ("professional mode", "van setu pro", "public mode")
    if any(k in msg_lower for k in ["professional mode", "van setu pro", "pro mode", "switch to pro", "professional studio"]):
        actions.append({
            "type": "SWITCH_MODE",
            "payload": {"mode": "professional"},
            "label": "Switch to Professional Studio (Van Setu Pro)",
            "requires_confirmation": False,
        })
        current_mode = "professional"
        notes.append("Switched workspace to **Professional Studio (Van Setu Pro)**.")
    elif any(k in msg_lower for k in ["public mode", "switch to public", "simple mode"]):
        actions.append({
            "type": "SWITCH_MODE",
            "payload": {"mode": "public"},
            "label": "Switch to Public Mode",
            "requires_confirmation": False,
        })
        current_mode = "public"
        notes.append("Switched workspace to **Public Mode**.")

    # 5. Detect corridor selection by rank ("select rank 1", "#1", "top corridor") or by name/ID
    rank_sel_match = re.search(r"(?:select|highlight|inspect|show|zoom to)\s+(?:rank\s*#?|#)(\d+)", msg_lower)
    matched_corridor = None
    if rank_sel_match and available_corridors:
        target_rank = int(rank_sel_match.group(1))
        for c in available_corridors:
            if c.get("rank") == target_rank:
                matched_corridor = c
                break
    elif any(k in msg_lower for k in ["top corridor", "highest priority", "number 1", "rank 1", "#1"]) and available_corridors:
        if any(v in msg_lower for v in ["select", "highlight", "inspect", "show", "zoom", "which", "what is"]):
            matched_corridor = available_corridors[0]
    else:
        for c in available_corridors:
            cname = str(c.get("name", "")).lower()
            cid = str(c.get("id", "")).lower()
            # Match distinct road tokens (e.g. "jafrabad", "grand trunk", "dilshad", "najafgarh", "anand vihar", "patel", "rohtak", "okhla")
            tokens = [t for t in re.split(r"[\s(),-]+", cname) if len(t) >= 4 and t not in ("road", "marg", "street", "main", "market", "delhi", "approach", "area")]
            if (cid and cid in msg_lower) or (cname and cname in msg_lower) or any(t in msg_lower for t in tokens):
                matched_corridor = c
                break

    if matched_corridor:
        actions.append({
            "type": "SELECT_CORRIDOR",
            "payload": {
                "corridor_id": matched_corridor.get("id"),
                "name": matched_corridor.get("name"),
            },
            "label": f"Select & Highlight {matched_corridor.get('name')} (#{matched_corridor.get('rank')})",
            "requires_confirmation": False,
        })
        selected_corridor = matched_corridor
        notes.append(
            f"Selected **{matched_corridor.get('name')}** (`{matched_corridor.get('id')}`, Rank **#{matched_corridor.get('rank')}**, Score **{matched_corridor.get('score', 0):.4f}**)."
        )

    # 6. Detect layer visibility toggles
    if any(k in msg_lower for k in ["show heat", "enable heat", "turn on heat", "heat layer", "lst layer"]):
        actions.append({
            "type": "TOGGLE_LAYER",
            "payload": {"layer": "lst", "enabled": True},
            "label": "Enable Heat (LST) Layer on Map",
            "requires_confirmation": False,
        })
        notes.append("Enabled the **Heat (MODIS LST)** raster overlay on the map.")
    if any(k in msg_lower for k in ["show ndvi", "enable ndvi", "turn on ndvi", "green cover layer", "vegetation layer"]):
        actions.append({
            "type": "TOGGLE_LAYER",
            "payload": {"layer": "ndvi", "enabled": True},
            "label": "Enable NDVI / Green Cover Layer on Map",
            "requires_confirmation": False,
        })
        notes.append("Enabled the **NDVI / Green Cover (Sentinel-2 10m)** raster overlay on the map.")
    if any(k in msg_lower for k in ["show gdi", "enable gdi", "priority layer", "gdi layer"]):
        actions.append({
            "type": "TOGGLE_LAYER",
            "payload": {"layer": "gdi", "enabled": True},
            "label": "Enable Priority Index (GDI) Layer on Map",
            "requires_confirmation": False,
        })
        notes.append("Enabled the **Green Deficit Index (GDI)** overlay on the map.")

    # 7. Detect workflow modal / panel triggers
    if any(k in msg_lower for k in ["community input", "submit community", "community form", "community suggestion"]):
        needs_confirm = "submit" in msg_lower and len(msg_lower) > 35
        actions.append({
            "type": "OPEN_MODAL",
            "payload": {"modal": "community_input"},
            "label": "Open Community Input Drawer",
            "requires_confirmation": needs_confirm,
        })
        notes.append("Opened the **Community Input** workflow drawer.")

    if any(k in msg_lower for k in ["health data", "health form", "submit health", "medical data", "heatstroke"]):
        actions.append({
            "type": "OPEN_MODAL",
            "payload": {"modal": "health_data"},
            "label": "Open Health Data Workflow",
            "requires_confirmation": False,
        })
        notes.append("Opened the **Health Data** workflow modal (with privacy & epidemiological correlation safeguards).")

    if any(k in msg_lower for k in ["feasibility", "constraint", "utility conflict", "footpath width", "budget"]):
        actions.append({
            "type": "OPEN_FEASIBILITY_PANEL",
            "payload": {"mode": "professional"},
            "label": "Open Professional Feasibility & Constraints Panel",
            "requires_confirmation": False,
        })
        notes.append("Opened the **Professional Feasibility & Constraints** configurator.")

    if any(k in msg_lower for k in ["intervention", "cost", "cpwd", "tree", "canopy", "bioswale", "shade"]):
        target_c = selected_corridor or (available_corridors[0] if available_corridors else None)
        if target_c:
            actions.append({
                "type": "REQUEST_INTERVENTION_ASSESSMENT",
                "payload": {"corridor_id": target_c.get("id"), "name": target_c.get("name")},
                "label": f"Inspect Interventions & CPWD Costing for {target_c.get('name')}",
                "requires_confirmation": False,
            })
            notes.append(f"Focused the **Intervention Suitability & CPWD DSR 2023 Lifecycle Cost** assessment for **{target_c.get('name')}**.")

    if any(k in msg_lower for k in ["report", "export", "download assessment", "prepare assessment"]):
        actions.append({
            "type": "EXPORT_REPORT",
            "payload": {"format": "markdown"},
            "label": "Generate & Download Reproducible Assessment Report",
            "requires_confirmation": False,
        })
        notes.append("Prepared and triggered the **Reproducible Corridor Assessment Report** download.")

    # Build grounded analytical reply
    target_c = selected_corridor if selected_corridor.get("name") else (available_corridors[0] if available_corridors else None)
    corridor_summary = ""
    if target_c:
        cname = target_c.get("name", "Selected Corridor")
        cscore = float(target_c.get("score") or target_c.get("priority_score") or 0.5)
        cheat = float(target_c.get("heat") or target_c.get("heat_norm") or 0.5)
        cndvi = float(target_c.get("ndvi") or target_c.get("ndvi_norm") or 0.3)
        crank = target_c.get("rank", 1)
        brank = target_c.get("baseline_rank", crank)
        rdelta = target_c.get("rank_change", 0)
        delta_str = f"+{rdelta}" if rdelta > 0 else str(rdelta)
        corridor_summary = (
            f"Currently inspecting **{cname}** (Rank **#{crank}**, Baseline Rank **#{brank}**, Δ **{delta_str}**): "
            f"`score = {current_hw:.2f} × Heat ({cheat:.4f}) + {(1.0 - current_hw):.2f} × (1 - NDVI ({cndvi:.4f})) = {cscore:.4f}`."
        )

    if notes:
        reply_text = " ".join(notes) + (f"\n\n{corridor_summary}" if corridor_summary else "")
    else:
        reply_text = (
            f"Active Workspace State: **{current_mode.title()} Mode** | Scenario: **{current_scenario}** | "
            f"`heat_weight = {current_hw:.2f}` (`green_deficit_weight = {(1.0 - current_hw):.2f}`). "
            f"{corridor_summary}\n\n"
            "You can ask me to change `heat_weight` (e.g., *'Set heat weight to 0.85'*), switch scenarios (*'Activate Heat-Focused scenario'*), "
            "highlight any corridor (*'Select Grand Trunk Road'*), toggle map overlays (*'Show Heat and NDVI layers'*), "
            "open *Community Input*, *Health Data*, or *Feasibility Constraints*, or *Export an Assessment Report*."
        )

    return {
        "reply": reply_text,
        "actions": actions,
    }


async def run_vansetu_ai_agent(
    user_message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute the Van Setu AI Action Agent.
    First parses deterministic, validated application actions; if PRUNE_API_KEY is configured,
    enriches the natural-language explanation via Prune/Gemini while keeping backend validation authoritative.
    """
    deterministic_result = parse_deterministic_agent_actions(user_message, context)
    settings = get_settings()
    api_key = os.environ.get("PRUNE_API_KEY") or settings.prune_api_key

    if not api_key or api_key in ("prune_your_key_here", ""):
        return {
            "status": "deterministic_fallback",
            "is_ai_generated": False,
            "provider": "deterministic-action-engine",
            "model_used": None,
            "reply": deterministic_result["reply"],
            "actions": deterministic_result["actions"],
            "notice": (
                "PRUNE_API_KEY is not set on the backend; executed actions via Van Setu's "
                "deterministic spatial action engine."
            ),
        }

    # When PRUNE_API_KEY is configured, query Prune/Gemini for a richer narrative while keeping validated actions
    base_url = (os.environ.get("PRUNE_BASE_URL") or settings.prune_base_url).rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    safe_context = {
        "mode": context.get("mode", "public"),
        "scenario": context.get("scenario", "balanced"),
        "heat_weight": context.get("heat_weight", 0.6),
        "selected_corridor": context.get("selected_corridor"),
        "top_corridors": (context.get("available_corridors") or [])[:5],
        "executed_actions": [a["label"] for a in deterministic_result["actions"]],
    }

    payload = {
        "model": settings.prune_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Van Setu Urban Climate AI Action Agent. "
                    "Never invent scores, rankings, or costs; use only the provided deterministic context. "
                    "Confirm any executed_actions concisely in 2-4 sentences."
                ),
            },
            {
                "role": "user",
                "content": f"User request: {user_message}\nWorkspace context & actions: {json.dumps(safe_context)}",
            },
        ],
        "temperature": 0.2,
        "max_tokens": 350,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "").strip()
                return {
                    "status": "success",
                    "is_ai_generated": True,
                    "provider": "prune-gemini",
                    "model_used": data.get("model", settings.prune_model),
                    "reply": content or deterministic_result["reply"],
                    "actions": deterministic_result["actions"],
                    "prune_metadata": data.get("prune_metadata"),
                }
    except Exception as exc:
        logger.warning(f"Prune AI agent call fell back to deterministic engine: {exc}")

    return {
        "status": "deterministic_fallback",
        "is_ai_generated": False,
        "provider": "deterministic-action-engine",
        "model_used": None,
        "reply": deterministic_result["reply"],
        "actions": deterministic_result["actions"],
    }
