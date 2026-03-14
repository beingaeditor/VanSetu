"""
VanSetu Telegram Bot — Community Data Collection

Allows citizens to submit environmental observations and health data
directly through Telegram, feeding into the VanSetu priority scoring engine.

Commands:
  /start          — Welcome message & menu
  /submit         — Start community data submission (guided conversation)
  /health         — Submit health department data
  /stats          — View platform statistics
  /submissions    — View recent community submissions
  /help           — Show available commands

Usage:
  python telegram_bot.py
"""

import os
import json
import logging
from datetime import datetime

import httpx
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ─── Configuration ──────────────────────────────────────────
BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8633648042:AAFkDnpZIR6XBl9C4YGmaUw4a5dSiyCnKUs",
)
API_BASE = os.environ.get("VANSETU_API_URL", "http://localhost:8000/api")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("VanSetuBot")

# ─── Conversation states (community submission) ─────────────
(
    WARD,
    STREET,
    USER_TYPE,
    HEAT_LEVEL,
    SHADE_LEVEL,
    PEDESTRIAN,
    PEAK_TIME,
    POLLUTION_LEVEL,
    POLLUTION_SOURCE,
    HEATWAVE_RISK,
    VULNERABLE_POP,
    EMERGENCY,
    CONFIRM,
) = range(13)

# ─── Conversation states (health submission) ────────────────
(
    H_DISTRICT,
    H_AREA,
    H_HEATSTROKE,
    H_DEHYDRATION,
    H_RESPIRATORY,
    H_EMERGENCY,
    H_VULNERABLE,
    H_RISK_LEVEL,
    H_CONFIRM,
) = range(20, 29)

# ─── Choice lists ───────────────────────────────────────────
WARDS = ["Ward 1", "Ward 2", "Ward 3"]
USER_TYPES = ["Street Vendor", "School", "College / University"]
HEAT_LEVELS = ["Comfortable", "Warm", "Very Hot", "Extremely Hot"]
SHADE_LEVELS = ["Full shade", "Partial shade", "Very little shade", "No shade"]
PEDESTRIAN_LEVELS = [
    "Low (<200 people/day)",
    "Medium (200–800 people/day)",
    "High (800–2000 people/day)",
    "Very High (>2000 people/day)",
]
PEAK_TIMES = ["Morning", "Afternoon", "Evening", "All Day"]
POLLUTION_LEVELS = ["Low", "Moderate", "High", "Severe"]
POLLUTION_SOURCES = [
    "Traffic corridor",
    "Market / commercial activity",
    "Industrial activity",
    "Mixed urban pollution",
]
HEATWAVE_RISKS = ["Low risk", "Moderate risk", "High risk", "Extreme heat risk zone"]
VULNERABLE_POPS = ["Low", "Moderate", "High", "Very High"]
EMERGENCY_LEVELS = ["None", "Occasional", "Frequent", "Critical hotspot"]

DISTRICTS = [
    "Central", "New Delhi", "North", "North East", "North West",
    "East", "West", "South", "South East", "South West", "Shahdara",
]
RISK_LEVELS = ["Low", "Moderate", "High", "Extreme"]


def _kb(choices, cols=2):
    """Build a reply keyboard from a list of choices."""
    rows = [choices[i : i + cols] for i in range(0, len(choices), cols)]
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)


# ═══════════════════════════════════════════════════════════
#  BASIC COMMANDS
# ═══════════════════════════════════════════════════════════


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with inline menu."""
    welcome = (
        "🌿 *Welcome to VanSetu Community Bot!*\n\n"
        "Help us map Delhi's green infrastructure needs by sharing "
        "your on-the-ground observations.\n\n"
        "📋 *What you can do:*\n"
        "• /submit — Report local heat, shade & pollution\n"
        "• /health — Submit health department data\n"
        "• /stats — View platform statistics\n"
        "• /submissions — View recent submissions\n"
        "• /help — Show all commands\n\n"
        "🏙️ _Your data feeds directly into VanSetu's Priority Index, "
        "helping planners decide where green corridors are needed most._"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all commands."""
    text = (
        "🌿 *VanSetu Bot Commands*\n\n"
        "/start — Welcome & menu\n"
        "/submit — Submit community observation\n"
        "/health — Submit health data\n"
        "/stats — Platform statistics\n"
        "/submissions — Recent submissions\n"
        "/cancel — Cancel current operation\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display platform statistics."""
    await update.message.reply_text("📡 Fetching statistics…")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            stats_res = await client.get(f"{API_BASE}/stats")
            aqi_res = await client.get(f"{API_BASE}/aqi/status")
            stats = stats_res.json()
            aqi = aqi_res.json()

        ndvi = stats.get("ndvi", {})
        lst = stats.get("lst", {})
        gdi = stats.get("gdi", {})

        text = (
            "📊 *VanSetu Platform Statistics*\n\n"
            f"🌿 *NDVI (Vegetation)*\n"
            f"   Mean: `{ndvi.get('mean', 0):.3f}`  |  "
            f"Range: `{ndvi.get('min', 0):.3f}` – `{ndvi.get('max', 0):.3f}`\n\n"
            f"🌡️ *LST (Temperature)*\n"
            f"   Mean: `{lst.get('mean', 0):.1f}°C`  |  "
            f"Range: `{lst.get('min', 0):.1f}` – `{lst.get('max', 0):.1f}°C`\n\n"
            f"📊 *GDI (Priority Index)*\n"
            f"   Mean: `{gdi.get('mean', 0):.3f}`  |  "
            f"Range: `{gdi.get('min', 0):.3f}` – `{gdi.get('max', 0):.3f}`\n\n"
            f"💨 *Air Quality*\n"
            f"   Avg PM2.5: `{aqi.get('average_pm25', '—')}`  |  "
            f"Stations: `{aqi.get('stations_count', 0)}`\n\n"
            f"_Last updated: {aqi.get('last_updated', 'N/A')}_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        await update.message.reply_text(
            "❌ Could not fetch statistics. Is the backend running?"
        )


async def submissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent community submissions."""
    await update.message.reply_text("📡 Fetching recent submissions…")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{API_BASE}/community-data")
            data = res.json()

        if not data:
            await update.message.reply_text("📭 No community submissions yet.")
            return

        # Show last 5
        recent = data[-5:]
        lines = ["📋 *Recent Community Submissions*\n"]
        for i, entry in enumerate(reversed(recent), 1):
            ward = entry.get("ward", "?")
            street = entry.get("street", "—")
            heat = entry.get("heatLevel", "?")
            pollution = entry.get("pollutionLevel", "?")
            ts = entry.get("submitted_at", "")[:16]
            lines.append(
                f"*{i}.* {ward}, {street}\n"
                f"   🔥 Heat: {heat}  |  💨 Pollution: {pollution}\n"
                f"   🕐 _{ts}_\n"
            )
        lines.append(f"\n_Total submissions: {len(data)}_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Submissions fetch failed: {e}")
        await update.message.reply_text(
            "❌ Could not fetch submissions. Is the backend running?"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
#  COMMUNITY DATA SUBMISSION CONVERSATION
# ═══════════════════════════════════════════════════════════


async def submit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin community data submission."""
    context.user_data["community"] = {"city": "Delhi"}
    await update.message.reply_text(
        "📝 *Community Observation Form*\n\n"
        "Let's collect your on-the-ground data.\n"
        "You can /cancel at any time.\n\n"
        "Select your *Ward*:",
        parse_mode="Markdown",
        reply_markup=_kb(WARDS, 3),
    )
    return WARD


async def submit_ward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["ward"] = update.message.text
    await update.message.reply_text(
        "📍 Enter the *Street / Area* name:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STREET


async def submit_street(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["street"] = update.message.text
    await update.message.reply_text(
        "👤 Select your *User Type*:",
        parse_mode="Markdown",
        reply_markup=_kb(USER_TYPES, 3),
    )
    return USER_TYPE


async def submit_user_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["userType"] = update.message.text
    await update.message.reply_text(
        "🔥 How hot does it feel in your area?\n*Heat Level*:",
        parse_mode="Markdown",
        reply_markup=_kb(HEAT_LEVELS, 2),
    )
    return HEAT_LEVEL


async def submit_heat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["heatLevel"] = update.message.text
    await update.message.reply_text(
        "🌳 How much shade is available?\n*Shade Level*:",
        parse_mode="Markdown",
        reply_markup=_kb(SHADE_LEVELS, 2),
    )
    return SHADE_LEVEL


async def submit_shade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["shadeLevel"] = update.message.text
    await update.message.reply_text(
        "🚶 How busy is pedestrian traffic?\n*Pedestrian Activity*:",
        parse_mode="Markdown",
        reply_markup=_kb(PEDESTRIAN_LEVELS, 1),
    )
    return PEDESTRIAN


async def submit_pedestrian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["pedestrianActivity"] = update.message.text
    await update.message.reply_text(
        "🕐 When is it busiest?\n*Peak Activity Time*:",
        parse_mode="Markdown",
        reply_markup=_kb(PEAK_TIMES, 2),
    )
    return PEAK_TIME


async def submit_peak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["peakTime"] = update.message.text
    await update.message.reply_text(
        "💨 Air pollution level in your area?\n*Pollution Level*:",
        parse_mode="Markdown",
        reply_markup=_kb(POLLUTION_LEVELS, 2),
    )
    return POLLUTION_LEVEL


async def submit_pollution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["pollutionLevel"] = update.message.text
    await update.message.reply_text(
        "🏭 What is the major pollution source?\n*Pollution Source*:",
        parse_mode="Markdown",
        reply_markup=_kb(POLLUTION_SOURCES, 1),
    )
    return POLLUTION_SOURCE


async def submit_pollution_src(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["pollutionSource"] = update.message.text
    await update.message.reply_text(
        "🌡️ Heatwave risk level in your area?",
        parse_mode="Markdown",
        reply_markup=_kb(HEATWAVE_RISKS, 2),
    )
    return HEATWAVE_RISK


async def submit_heatwave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["heatwaveRisk"] = update.message.text
    await update.message.reply_text(
        "👶 Vulnerable population (elderly, children, outdoor workers)?",
        parse_mode="Markdown",
        reply_markup=_kb(VULNERABLE_POPS, 2),
    )
    return VULNERABLE_POP


async def submit_vulnerable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["vulnerablePopulation"] = update.message.text
    await update.message.reply_text(
        "🚑 Emergency heat incidents in your area?",
        parse_mode="Markdown",
        reply_markup=_kb(EMERGENCY_LEVELS, 2),
    )
    return EMERGENCY


async def submit_emergency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["community"]["emergencyHeatIncidents"] = update.message.text
    d = context.user_data["community"]

    summary = (
        "✅ *Review your submission:*\n\n"
        f"📍 *Location:* {d['city']}, {d['ward']}, {d.get('street', '—')}\n"
        f"👤 *User Type:* {d['userType']}\n"
        f"🔥 *Heat:* {d['heatLevel']}  |  🌳 *Shade:* {d['shadeLevel']}\n"
        f"🚶 *Pedestrians:* {d['pedestrianActivity']}\n"
        f"🕐 *Peak Time:* {d['peakTime']}\n"
        f"💨 *Pollution:* {d['pollutionLevel']} ({d['pollutionSource']})\n"
        f"🌡️ *Heatwave Risk:* {d['heatwaveRisk']}\n"
        f"👶 *Vulnerable Pop:* {d['vulnerablePopulation']}\n"
        f"🚑 *Emergencies:* {d['emergencyHeatIncidents']}\n\n"
        "Send *Yes* to submit or *No* to cancel."
    )
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=_kb(["Yes ✅", "No ❌"], 2),
    )
    return CONFIRM


async def submit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "yes" not in update.message.text.lower():
        await update.message.reply_text(
            "❌ Submission cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    d = context.user_data["community"]
    await update.message.reply_text(
        "📡 Submitting to VanSetu…", reply_markup=ReplyKeyboardRemove()
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(f"{API_BASE}/community-data", json=d)
            result = res.json()

        await update.message.reply_text(
            f"✅ *Submitted successfully!*\n\n"
            f"ID: `{result.get('id', '?')}`\n"
            f"📝 {result.get('message', 'Recorded')}\n\n"
            f"_Thank you for contributing to VanSetu!_ 🌿",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Submission failed: {e}")
        await update.message.reply_text(
            "❌ Submission failed. Please make sure the backend is running and try again."
        )

    context.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
#  HEALTH DATA SUBMISSION CONVERSATION
# ═══════════════════════════════════════════════════════════


async def health_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin health data submission."""
    context.user_data["health"] = {}
    await update.message.reply_text(
        "🏥 *Health Data Submission*\n\n"
        "Submit heat-related health data for corridor prioritization.\n"
        "You can /cancel at any time.\n\n"
        "Select *District*:",
        parse_mode="Markdown",
        reply_markup=_kb(DISTRICTS, 3),
    )
    return H_DISTRICT


async def health_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["health"]["district"] = update.message.text
    await update.message.reply_text(
        "📍 Enter the *Area / Locality* name (e.g. Chandni Chowk):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return H_AREA


async def health_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["health"]["area"] = update.message.text
    await update.message.reply_text(
        "🤒 Number of *heatstroke cases* (enter a number):",
        parse_mode="Markdown",
    )
    return H_HEATSTROKE


async def health_heatstroke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["health"]["heatstroke_cases"] = int(update.message.text)
    except ValueError:
        context.user_data["health"]["heatstroke_cases"] = 0
    await update.message.reply_text(
        "💧 Number of *dehydration cases*:", parse_mode="Markdown"
    )
    return H_DEHYDRATION


async def health_dehydration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["health"]["dehydration_cases"] = int(update.message.text)
    except ValueError:
        context.user_data["health"]["dehydration_cases"] = 0
    await update.message.reply_text(
        "🫁 Number of *respiratory cases*:", parse_mode="Markdown"
    )
    return H_RESPIRATORY


async def health_respiratory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["health"]["respiratory_cases"] = int(update.message.text)
    except ValueError:
        context.user_data["health"]["respiratory_cases"] = 0
    await update.message.reply_text(
        "🚑 Number of *emergency visits*:", parse_mode="Markdown"
    )
    return H_EMERGENCY


async def health_emergency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["health"]["emergency_visits"] = int(update.message.text)
    except ValueError:
        context.user_data["health"]["emergency_visits"] = 0
    await update.message.reply_text(
        "👶 *Vulnerable population percentage* (0–100):", parse_mode="Markdown"
    )
    return H_VULNERABLE


async def health_vulnerable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text)
        context.user_data["health"]["vulnerable_population_pct"] = max(0, min(100, val))
    except ValueError:
        context.user_data["health"]["vulnerable_population_pct"] = 0
    await update.message.reply_text(
        "🌡️ *Heat Risk Classification*:",
        parse_mode="Markdown",
        reply_markup=_kb(RISK_LEVELS, 2),
    )
    return H_RISK_LEVEL


async def health_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["health"]["heat_risk_level"] = update.message.text
    d = context.user_data["health"]
    total = (
        d.get("heatstroke_cases", 0)
        + d.get("dehydration_cases", 0)
        + d.get("respiratory_cases", 0)
    )

    summary = (
        "✅ *Review health data:*\n\n"
        f"📍 *District:* {d['district']}, {d.get('area', '—')}\n"
        f"🤒 Heatstroke: {d.get('heatstroke_cases', 0)}\n"
        f"💧 Dehydration: {d.get('dehydration_cases', 0)}\n"
        f"🫁 Respiratory: {d.get('respiratory_cases', 0)}\n"
        f"🚑 Emergency: {d.get('emergency_visits', 0)}\n"
        f"👶 Vulnerable: {d.get('vulnerable_population_pct', 0)}%\n"
        f"🌡️ Risk Level: {d.get('heat_risk_level', '?')}\n"
        f"📊 Total cases: {total}\n\n"
        "Send *Yes* to submit or *No* to cancel."
    )
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=_kb(["Yes ✅", "No ❌"], 2),
    )
    return H_CONFIRM


async def health_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "yes" not in update.message.text.lower():
        await update.message.reply_text(
            "❌ Submission cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    d = context.user_data["health"]
    await update.message.reply_text(
        "📡 Submitting health data…", reply_markup=ReplyKeyboardRemove()
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(f"{API_BASE}/health-data", json=d)
            result = res.json()

        await update.message.reply_text(
            f"✅ *Health data submitted!*\n\n"
            f"ID: `{result.get('id', '?')}`\n"
            f"📝 {result.get('message', 'Recorded')}\n\n"
            f"_Thank you for contributing to VanSetu!_ 🏥",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Health submission failed: {e}")
        await update.message.reply_text(
            "❌ Submission failed. Please make sure the backend is running and try again."
        )

    context.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════


def main():
    """Start the bot."""
    print("=" * 50)
    print("🤖 VanSetu Telegram Bot")
    print(f"   API: {API_BASE}")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("submissions", submissions_command))

    # Community data conversation
    community_conv = ConversationHandler(
        entry_points=[CommandHandler("submit", submit_start)],
        states={
            WARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ward)],
            STREET: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_street)],
            USER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_user_type)],
            HEAT_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_heat)],
            SHADE_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_shade)],
            PEDESTRIAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pedestrian)],
            PEAK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_peak)],
            POLLUTION_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pollution)],
            POLLUTION_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pollution_src)],
            HEATWAVE_RISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_heatwave)],
            VULNERABLE_POP: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_vulnerable)],
            EMERGENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_emergency)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(community_conv)

    # Health data conversation
    health_conv = ConversationHandler(
        entry_points=[CommandHandler("health", health_start)],
        states={
            H_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_district)],
            H_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_area)],
            H_HEATSTROKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_heatstroke)],
            H_DEHYDRATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_dehydration)],
            H_RESPIRATORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_respiratory)],
            H_EMERGENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_emergency)],
            H_VULNERABLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_vulnerable)],
            H_RISK_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_risk)],
            H_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, health_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(health_conv)

    print("\n🟢 Bot is running. Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
