# 🧠 MASTER IMPLEMENTATION PROMPT

## **FEATURE: BEFORE–AFTER CORRIDOR VISUAL (CONCEPTUAL MOCKUP)**

> **IMPORTANT:**
> This feature is **purely visual and conceptual**.
> Do NOT simulate temperature, AQI, or vegetation growth.
> Do NOT add new datasets.

---

## ROLE & EXPECTATION

You are a **senior frontend-focused full-stack engineer** working on an urban planning visualization platform.

Your task is to add a **Before–After visual/mockup** for a **selected corridor**, clearly showing:

* Existing street condition (**Before**)
* Proposed green intervention (**After**)

This must:

* Reuse existing corridor geometry
* Match the corridor’s **recommended intervention type**
* Be visually clear, honest, and presentation-ready

---

## EXISTING SYSTEM (ASSUME THIS IS TRUE)

### Frontend

* React (Vite)
* Interactive map (Mapbox GL JS or Leaflet)
* Corridor click:

  * Zooms to corridor
  * Opens right-side panel
  * Shows recommended interventions
* Corridor geometry available as GeoJSON

### Backend

* No backend changes required for this feature

---

## FEATURE OBJECTIVE

Upgrade the right-side corridor panel to include:

> **A simple “Before / After” visual illustrating the proposed change**

This must satisfy the problem statement requirement:

> “Shows a simple before-and-after visual or mockup of the proposed change”

---

## PART 1 — VISUAL CONCEPT (MANDATORY RULES)

### BEFORE VIEW

* Base map only (OSM style)
* Corridor highlighted using:

  * Existing exposure / priority coloring
* No added greenery
* Muted colors

### AFTER VIEW

* Same map view
* Same corridor geometry
* Add **conceptual green overlays** based on intervention type:

  * Icons
  * Semi-transparent polygons
* No numerical claims
* No environmental simulation

⚠️ Both views must be:

* Same zoom
* Same orientation
* Same corridor extent

---

## PART 2 — INTERVENTION → VISUAL MAPPING

Use the corridor’s existing `corridor_type`.

### Heat-dominated corridor

Add:

* Tree icons 🌳 spaced along sidewalks
* Soft green canopy overlay (30–40% opacity)
* Optional dashed shaded walkway line

---

### Pollution-dominated corridor

Add:

* Dense green buffer polygons along road edge
* Vertical green screen icons
* Clear separation from carriageway

---

### Green-deficit / connectivity corridor

Add:

* Small pocket-green polygons at intervals
* Light green cycling / walking path overlay
* Minimal tree icons

---

### Mixed-exposure corridor

Add:

* Combination of trees + buffer elements
* Keep visuals minimal (avoid clutter)

---

## PART 3 — FRONTEND IMPLEMENTATION

### 1️⃣ ADD “BEFORE / AFTER” TO RIGHT PANEL

In the existing right-side panel, add a new section:

```
[ Conceptual Corridor Improvement ]

[ BEFORE | AFTER ]   ← toggle buttons
```

* Default state: **Before**
* Clicking **After** switches the map overlay

---

### 2️⃣ MAP OVERLAY LOGIC

* BEFORE:

  * Show existing corridor styling only
* AFTER:

  * Add a new map layer:

    * `intervention_overlay`
  * This layer:

    * Uses the same corridor geometry
    * Adds icons / polygons based on corridor type

This must be:

* Purely client-side
* No API calls
* No data mutation

---

### 3️⃣ ANIMATION REQUIREMENTS

* Toggle transition:

  * Fade out old layer (200–300ms)
  * Fade in new layer (200–300ms)
* No map jump
* No zoom change

Animations should feel **subtle and professional**, not flashy.

---

## PART 4 — LABELING & HONESTY (IMPORTANT)

### Add small caption under the visual:

> **"Conceptual illustration of a proposed VanSetu corridor intervention"**

Optional tooltip:

> “This is a visual mockup, not an environmental simulation.”

This protects you during judging.

---

## PART 5 — UX RULES

* Visual must not clutter the panel
* Icons must scale with zoom
* Panel scroll must still work
* Closing the panel:

  * Removes intervention overlay
  * Restores original corridor styling

---

## WHAT NOT TO DO

❌ Do not show temperature reduction
❌ Do not show AQI improvement
❌ Do not show 3D renders
❌ Do not change street layout
❌ Do not add timelines or costs

This is a **visual aid**, not a forecast.

---

## EXPECTED END STATE

User flow:

1. User clicks a corridor
2. Right panel opens
3. User sees intervention suggestion
4. User switches:

   * BEFORE → AFTER
5. Map visually shows:

   * What exists
   * What is proposed
6. User clearly understands the intent

This completes the problem statement perfectly.

---

## FINAL INSTRUCTION

Implement this cleanly and minimally.

At the end:

* Add a short README note:
  **“Before–after visuals are conceptual and illustrative.”**

---

## NOW IMPLEMENT THIS FEATURE.