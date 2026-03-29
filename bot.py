import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv()

TOKEN = os.getenv("TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN:
    raise Exception("❌ TOKEN missing")

if not RAPIDAPI_KEY:
    raise Exception("❌ RAPIDAPI_KEY missing")

# ---------------- SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
}

TIMEZONE = pytz.timezone("Asia/Kolkata")


# ---------------- FETCH ----------------
def get_ipl_matches(endpoint):
    try:
        url = f"https://cricbuzz-cricket.p.rapidapi.com/matches/v1/{endpoint}"
        res = requests.get(url, headers=HEADERS, timeout=8)

        if res.status_code != 200:
            return []

        data = res.json()
        matches = []

        for t in data.get("typeMatches", []):
            for series in t.get("seriesMatches", []):
                wrapper = series.get("seriesAdWrapper")

                if not wrapper:
                    continue

                name = wrapper.get("seriesName", "").lower()

                if any(term in name for term in [
                    "ipl",
                    "indian premier league",
                    "tata ipl"
                ]):
                    matches.extend(wrapper.get("matches", []))

        return matches

    except:
        return []


# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if CHANNEL_ID:
        auto_update.start()


# ---------------- COMMAND: SCORE (FIXED LOGIC) ----------------
@bot.command()
async def score(ctx):
    now = datetime.now(TIMEZONE)

    live_matches = get_ipl_matches("live")
    upcoming_matches = get_ipl_matches("upcoming")
    recent_matches = get_ipl_matches("recent")

    match = None

    # 🟢 1. LIVE MATCH FIRST
    if live_matches:
        match = live_matches[0]

    # 🔵 2. TODAY MATCH (UPCOMING)
    if not match and upcoming_matches:
        for m in upcoming_matches:
            ts = int(m.get("matchInfo", {}).get("startDate", 0))
            if ts == 0:
                continue

            start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

            if start.date() == now.date():
                match = m
                break

    # 🟠 3. TODAY MATCH (RECENT — toss/just started)
    if not match and recent_matches:
        for m in recent_matches:
            ts = int(m.get("matchInfo", {}).get("startDate", 0))
            if ts == 0:
                continue

            start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

            if start.date() == now.date():
                match = m
                break

    # 🔴 LAST fallback
    if not match and recent_matches:
        match = recent_matches[0]

    if not match:
        await ctx.send("❌ No IPL data found")
        return

    info = match.get("matchInfo", {})
    score = match.get("matchScore", {})

    t1 = info.get("team1", {}).get("teamName", "Team 1")
    t2 = info.get("team2", {}).get("teamName", "Team 2")

    status = info.get("status", "Match update")

    ts = int(info.get("startDate", 0))
    start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

    embed = discord.Embed(
        title="🏏 IPL Live Update",
        color=discord.Color.green()
    )

    text = f"**{t1} vs {t2}**\n\n"
    text += f"📢 {status}\n\n"
    text += f"🕒 {start.strftime('%d %B, %I:%M %p IST')}\n\n"

    if "team1Score" in score:
        s = score["team1Score"].get("inngs1", {})
        text += f"{t1}: {s.get('runs','-')}/{s.get('wickets','-')} ({s.get('overs','-')} ov)\n"

    if "team2Score" in score:
        s = score["team2Score"].get("inngs1", {})
        text += f"{t2}: {s.get('runs','-')}/{s.get('wickets','-')} ({s.get('overs','-')} ov)\n"

    embed.add_field(name="📊 Match Info", value=text, inline=False)

    await ctx.send(embed=embed)


# ---------------- COMMAND: UPCOMING ----------------
@bot.command()
async def upcoming(ctx):
    matches = get_ipl_matches("upcoming")
    now = datetime.now(TIMEZONE)

    for m in matches:
        ts = int(m.get("matchInfo", {}).get("startDate", 0))
        if ts == 0:
            continue

        start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

        if start > now:
            info = m["matchInfo"]

            embed = discord.Embed(title="📅 Next Match", color=discord.Color.blue())
            embed.add_field(
                name=f"{info['team1']['teamName']} vs {info['team2']['teamName']}",
                value=f"⏰ {start.strftime('%I:%M %p IST')}",
                inline=False
            )

            await ctx.send(embed=embed)
            return

    await ctx.send("❌ No upcoming IPL matches")


# ---------------- COMMAND: TODAY ----------------
@bot.command()
async def today(ctx):
    matches = get_ipl_matches("upcoming")
    today_date = datetime.now(TIMEZONE).date()

    embed = discord.Embed(title="📆 Today's Matches", color=discord.Color.orange())

    found = False

    for m in matches:
        ts = int(m.get("matchInfo", {}).get("startDate", 0))
        if ts == 0:
            continue

        start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

        if start.date() == today_date:
            info = m["matchInfo"]

            embed.add_field(
                name=f"{info['team1']['teamName']} vs {info['team2']['teamName']}",
                value=f"⏰ {start.strftime('%I:%M %p IST')}",
                inline=False
            )
            found = True

    if not found:
        await ctx.send("❌ No IPL matches today")
        return

    await ctx.send(embed=embed)


# ---------------- AUTO POST ----------------
@tasks.loop(hours=6)
async def auto_update():
    try:
        channel = bot.get_channel(int(CHANNEL_ID))
        if not channel:
            return

        matches = get_ipl_matches("upcoming")

        if matches:
            m = matches[0]
            info = m["matchInfo"]

            ts = int(info.get("startDate", 0))
            start = datetime.fromtimestamp(ts / 1000, tz=TIMEZONE)

            await channel.send(
                f"📢 Upcoming Match:\n"
                f"**{info['team1']['teamName']} vs {info['team2']['teamName']}**\n"
                f"⏰ {start.strftime('%I:%M %p IST')}"
            )

    except Exception as e:
        print("Auto error:", e)


# ---------------- RUN ----------------
bot.run(TOKEN)