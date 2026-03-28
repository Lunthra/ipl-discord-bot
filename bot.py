import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup

from dotenv import load_dotenv
import os

load_dotenv()

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# ---------------- COMMAND ----------------
@bot.command()
async def score(ctx):
    try:
        matches = []
        source = "RapidAPI"

        # ================= RAPIDAPI (LIVE + RECENT) =================
        try:
            url = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/recent"

            headers = {
                "X-RapidAPI-Key": "94f5f951f0msh8bcfa381afdc324p1420f8jsn9e76576ef411",
                "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
            }

            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()

            # 🔥 FLEXIBLE IPL FILTER + SAFE LOOP
            for t in data.get("typeMatches", []):
                for series in t.get("seriesMatches", []):
                    wrapper = series.get("seriesAdWrapper")
                    if not wrapper:
                        continue

                    series_name = wrapper.get("seriesName", "").lower()

                    if any(term in series_name for term in [
                        "ipl", "indian premier league", "tata ipl"
                    ]):
                        matches.extend(wrapper.get("matches", []))

        except Exception as e:
            print("RapidAPI error:", e)

        # ================= FALLBACK (ALL MATCHES) =================
        if not matches:
            try:
                url = "https://cricbuzz-live.vercel.app/v1/matches/recent"
                res = requests.get(url, timeout=5)

                data = res.json()
                raw = data.get("data")

                if isinstance(raw, dict):
                    matches = raw.get("matches", [])
                else:
                    matches = raw or []

                source = "Fallback"

            except Exception as e:
                print("Fallback error:", e)

        # ================= STILL NOTHING =================
        if not matches:
            await ctx.send("❌ No cricket data available (API issue)")
            return

        # 🔥 IMPORTANT FIX: SORT → GET LATEST MATCH
        matches = sorted(
            matches,
            key=lambda m: m.get("matchInfo", {}).get("startDate", 0),
            reverse=True
        )

        match = matches[0]

        embed = discord.Embed(
            title="🏏 IPL Match Update",
            color=discord.Color.green()
        )

        # ================= FORMAT (RAPIDAPI STRUCTURE) =================
        if "matchInfo" in match:
            info = match["matchInfo"]
            score = match.get("matchScore", {})

            t1 = info["team1"]["teamName"]
            t2 = info["team2"]["teamName"]

            text = f"**{t1} vs {t2}**\n"

            if "team1Score" in score:
                s = score["team1Score"]["inngs1"]
                text += f"{t1}: {s['runs']}/{s['wickets']} ({s['overs']} ov)\n"

            if "team2Score" in score:
                s = score["team2Score"]["inngs1"]
                text += f"{t2}: {s['runs']}/{s['wickets']} ({s['overs']} ov)\n"

            status = info.get("status", "Match update")

        # ================= FORMAT (FALLBACK STRUCTURE) =================
        else:
            title = match.get("title", "Match")
            teams = match.get("teams", [])
            overview = match.get("overview", "")

            text = f"**{title}**\n"

            for t in teams:
                name = t.get("team", "Unknown")
                run = t.get("run", "—")
                text += f"{name}: {run}\n"

            status = overview if overview else "Match update"

        embed.add_field(
            name=f"📊 Source: {source}",
            value=f"{text}\n🏆 {status}",
            inline=False
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        print("FULL ERROR:", e)

# ----------- KEEP ALIVE SERVER -----------
from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()
        
# ---------------- RUN BOT ----------------
import os
bot.run(os.getenv("TOKEN"))