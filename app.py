"""
NEU Chatbot — Flask app with OAuth login + chat persistence
"""

import re
import json
import uuid
import logging
import os
from datetime import datetime, timezone, timedelta
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

import requests as req_lib
from bs4 import BeautifulSoup
from flask import (Flask, request, jsonify,
                   session, redirect, url_for, send_from_directory)
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from groq import Groq

import db as DB

# ─── App setup ────────────────────────────────────────────────────────────────

REACT_BUILD = os.path.join(os.path.dirname(__file__), "frontend", "dist")

app = Flask(__name__, static_folder=REACT_BUILD, static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")
IS_VERCEL = bool(os.getenv("VERCEL"))
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = IS_VERCEL
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_PATH"]    = "/"
app.config["SERVER_NAME"]             = None
app.config["PREFERRED_URL_SCHEME"]    = "https" if IS_VERCEL else "http"
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "https://neu-chatbot.vercel.app",
    "https://neu-chatbot-goker-2705s-projects.vercel.app",
])

DB.init_db()
logging.basicConfig(level=logging.WARNING)
logging.getLogger("live_indexer").setLevel(logging.INFO)

# ─── OAuth ────────────────────────────────────────────────────────────────────

oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _ensure_user_in_db():
    """On Vercel, /tmp DB is ephemeral. Re-create user from session cookie."""
    uid = session.get("user_id")
    if uid and not DB.get_user(uid):
        DB.upsert_user(uid, session.get("user_name", "User"),
                        session.get("user_email", ""),
                        session.get("user_avatar", ""), "google")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/") or request.path == "/chat":
                return jsonify({"error": "not authenticated"}), 401
            return redirect("/login")
        _ensure_user_in_db()
        return f(*args, **kwargs)
    return decorated


def current_user():
    uid = session.get("user_id")
    return DB.get_user(uid) if uid else None


# ─── RAG / Vector DB ──────────────────────────────────────────────────────────

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "quickstart")
EMBED_MODEL    = "all-MiniLM-L6-v2"
TOP_K          = 8          # more chunks → richer context
MAX_HISTORY  = 14         # cap messages sent to LLM to avoid token overflow
MODEL        = "llama-3.3-70b-versatile"
HEADERS      = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

groq_client  = Groq(api_key=os.getenv("GROQ_API_KEY"))
CACHE_TTL    = 120        # 2-min cache for live data

SYSTEM_PROMPT = """You are **NEU Assistant** — a sharp, proactive campus advisor and academic copilot for Northeastern University. You combine a live knowledge base, real-time campus data, and Canvas LMS integration to give students accurate, actionable, and personalized assistance.

## Ground Rules

1. **Context is king.** Draw from RAG chunks, LIVE DATA, and CANVAS DATA sections provided. Never invent facts, deadlines, or grades.
2. **LIVE DATA & CANVAS DATA** contain real-time values — quote them exactly. Never fabricate due dates or assignment titles.
3. **If the context doesn't cover it**, say so clearly and point to the right resource.
4. **Cite sources** when using knowledge base chunks.

## Response Format

Use **Markdown** in every reply:
- **Bold** for due dates, deadlines, course names, urgency labels
- Bullet/numbered lists for task sequences and options
- `##` headers for multi-section answers
- Urgency emoji: 🔴 Critical (< 24h) · 🟠 High (< 48h) · 🟡 Medium (< 7d) · 🟢 Low

## Academic Intelligence (Canvas)

When CANVAS DATA is provided:
- Highlight the most urgent items first
- Group by course when showing multiple items
- Recommend a specific action order based on deadlines and likely effort
- Warn about overlapping deadlines proactively
- If Canvas is not connected, say: "Your Canvas account isn't connected yet. Head to the **Dashboard** to connect it."

## WhatsApp Reminders

When the user asks to be reminded about something:
- Confirm what will be sent and when
- Keep WhatsApp messages short, clear, and actionable
- Never send duplicate reminders for the same item

## Personality

- Warm but efficient — like a knowledgeable senior RA
- Proactive: if you see a conflict, tight deadline, or low parking, mention it
- Never overwhelming — prioritize ruthlessly, surface only what matters

## Topic Coverage

Admissions · Financial aid · Co-op programs · Academic policies · Course registration · Housing · Dining · Campus events · Parking · Transit · Campus news · Research opportunities · Student services · Canvas assignments & deadlines"""

HF_TOKEN     = os.getenv("HF_TOKEN", "")
HF_EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 384-dim, works on HF free inference

def embed_query(text):
    """Embed query via HuggingFace Inference API (free with token)."""
    r = req_lib.post(
        f"https://router.huggingface.co/hf-inference/models/{HF_EMBED_MODEL}",
        json={"inputs": text},
        headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

# ─── Pinecone REST client (no SDK needed) ────────────────────────────────────

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST    = os.getenv("PINECONE_HOST", "")

def _pinecone_host():
    """Get Pinecone index host, auto-discover if not set."""
    global PINECONE_HOST
    if PINECONE_HOST:
        return PINECONE_HOST
    r = req_lib.get("https://api.pinecone.io/indexes",
                    headers={"Api-Key": PINECONE_API_KEY}, timeout=10)
    r.raise_for_status()
    indexes = r.json().get("indexes", [])
    for idx in indexes:
        if idx["name"] == PINECONE_INDEX:
            PINECONE_HOST = f"https://{idx['host']}"
            return PINECONE_HOST
    raise RuntimeError(f"Pinecone index '{PINECONE_INDEX}' not found")

def pinecone_query(vector, top_k=TOP_K):
    host = _pinecone_host()
    r = req_lib.post(f"{host}/query",
                     headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
                     json={"vector": vector, "topK": top_k, "includeMetadata": True},
                     timeout=15)
    r.raise_for_status()
    return r.json()

def pinecone_stats():
    host = _pinecone_host()
    r = req_lib.get(f"{host}/describe_index_stats",
                    headers={"Api-Key": PINECONE_API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()

_indexer = None
if not os.getenv("VERCEL"):
    print("Connecting to Pinecone...", end=" ", flush=True)
    try:
        _pinecone_host()
        print(f"OK (index: {PINECONE_INDEX}, host: {PINECONE_HOST})")
    except Exception as e:
        print(f"Warning: {e}")

    # Live Indexer (background refresh) — local only
    try:
        import live_indexer as _indexer
        _indexer.start(refresh_hours=6)
    except ImportError:
        pass

# ─── Live data ────────────────────────────────────────────────────────────────

PARKING_PAGES = {
    "West Village Garage":     "https://masparc.com/west-village-garage",
    "Renaissance Park Garage": "https://masparc.com/renaissance-park-garage",
    "Gainsborough Garage":     "https://masparc.com/gainsborough-garage",
    "Columbus Garage":         "https://masparc.com/columbus-garage",
    "NUOakland":               "https://masparc.com/nuoakland",
}
PARKING_KW = re.compile(
    r"\b(park(?:ing)?|garage|spaces?|availab(?:le|ility)|lot|permit|capacity|spot|car|vehicle|drive|driving)\b", re.I)
EVENTS_KW  = re.compile(
    r"\b(events?|lecture|seminar|workshop|talk|conference|panel|today|tonight|upcoming|happening|schedule|calendar|things? to do|what'?s on|activities?|club)\b", re.I)
NEWS_KW    = re.compile(
    r"\b(news|research|discovery|article|latest|recently|announced|stories|headlines|update|press|publication)\b", re.I)
WEATHER_KW = re.compile(
    r"\b(weather|rain(?:ing)?|snow(?:ing)?|cold|hot|warm|temperature|forecast|umbrella|outside|outdoors|sunny|cloudy|wind(?:y)?|storm|coat|jacket)\b", re.I)
DINING_KW  = re.compile(
    r"\b(dining|food|eat(?:ing)?|lunch|dinner|breakfast|caf[eé]|cafeteria|meal|menu|restaurant|hungry|hours?|open|clos(?:ed|ing)|sushi|starbucks|int[e']l house)\b", re.I)
TRANSIT_KW = re.compile(
    r"\b(shuttle|bus|mbta|train|transit|transport(?:ation)?|commute|green line|orange line|subway|t(?:\s+stop)?|ride|get to|travel|walk(?:ing)?)\b", re.I)

_caches = {"parking": {}, "events": {}, "news": {}, "weather": {}, "dining": {}}


def _cached(key, ttl, fetcher):
    c = _caches[key]
    now = datetime.now()
    if c.get("ts") and (now - c["ts"]).seconds < ttl:
        return c["data"], c.get("extra", [])
    data, extra = fetcher()
    _caches[key] = {"data": data, "extra": extra, "ts": now}
    return data, extra


def _fetch_parking():
    lines = [f"LIVE PARKING (as of {datetime.now().strftime('%I:%M %p')}):\n"]
    cards = []
    for name, url in PARKING_PAGES.items():
        try:
            soup   = BeautifulSoup(req_lib.get(url, headers=HEADERS, timeout=8).text, "lxml")
            for t in soup(["script","style","nav","footer"]): t.decompose()
            tlines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
            spaces = None
            for i, l in enumerate(tlines):
                if "available spaces" in l.lower():
                    val = tlines[i+1] if i+1 < len(tlines) else ""
                    spaces = val if val.isdigit() else None
                    if not spaces:
                        m = re.search(r"(\d+)", l)
                        if m: spaces = m.group(1)
                    break
            hours = " · ".join(l for l in tlines if re.search(r"\d+:\d{2}\s*(AM|PM)", l, re.I))[:120]
            lines.append(f"• {name}: {spaces or 'N/A'} spaces | {hours or 'see site'} | {url}")
            cards.append({"name": name, "spaces": spaces, "hours": hours, "url": url})
        except Exception as e:
            lines.append(f"• {name}: error ({e})")
            cards.append({"name": name, "spaces": None, "hours": "", "url": url})
    return "\n".join(lines), cards


def _fetch_events():
    events = []
    try:
        r    = req_lib.get("https://events.northeastern.edu", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
        seen = set()
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                items = json.loads(script.string)
                if not isinstance(items, list): items = [items]
                for item in items:
                    if item.get("@type") == "Event":
                        name = item.get("name", "")
                        if name in seen or not name: continue
                        seen.add(name)
                        start = item.get("startDate", "")
                        loc   = (item.get("location") or {})
                        place = loc.get("name", "") if isinstance(loc, dict) else ""
                        url   = item.get("url", "https://events.northeastern.edu")
                        desc  = item.get("description", "")[:150]
                        try:
                            dt = datetime.fromisoformat(start)
                            formatted = dt.strftime("%a, %b %d · %I:%M %p")
                        except Exception:
                            formatted = start
                        events.append({"name": name, "date": formatted, "place": place, "url": url, "desc": desc})
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"Events error: {e}")
    events = events[:15]
    lines  = [f"LIVE EVENTS (as of {datetime.now().strftime('%I:%M %p')}):\n"]
    for e in events:
        lines.append(f"• {e['name']} | {e['date']} @ {e['place'] or 'NEU'} | {e['url']}")
    return "\n".join(lines), events


def _fetch_news():
    articles = []
    try:
        r    = req_lib.get("https://news.northeastern.edu", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
        seen = set()
        for tag in soup.find_all(["h2","h3"]):
            a = tag.find("a", href=True)
            if a and "northeastern.edu" in a["href"]:
                title = a.get_text(strip=True)
                if title in seen or len(title) < 15: continue
                seen.add(title)
                parent = tag.find_parent()
                desc   = ""
                if parent:
                    p = parent.find("p")
                    if p: desc = p.get_text(strip=True)[:140]
                articles.append({"title": title, "url": a["href"], "desc": desc})
    except Exception as e:
        logging.warning(f"News error: {e}")
    articles = articles[:10]
    lines    = [f"LIVE NEWS (as of {datetime.now().strftime('%I:%M %p')}):\n"]
    for a in articles:
        lines.append(f"• {a['title']} | {a['url']}")
    return "\n".join(lines), articles


def _fetch_weather():
    """Current Boston weather + 12-hour forecast via wttr.in (no API key)."""
    try:
        r    = req_lib.get("https://wttr.in/Boston,MA?format=j1", headers=HEADERS, timeout=8)
        raw  = r.json()
        data = raw.get("data", raw)   # wttr.in wraps in {"data": {...}}
        cur  = data["current_condition"][0]
        desc     = cur["weatherDesc"][0]["value"]
        temp_f   = cur["temp_F"]
        temp_c   = cur["temp_C"]
        feels_f  = cur["FeelsLikeF"]
        humidity = cur["humidity"]
        wind_mph = cur["windspeedMiles"]
        vis_mi   = cur["visibility"]

        # Next few hourly slots today
        hourly = data["weather"][0]["hourly"]
        fcast  = []
        for h in hourly[:5]:
            htime = int(h["time"]) // 100
            label = f"{htime:02d}:00" if htime < 24 else "00:00"
            hdesc = h["weatherDesc"][0]["value"]
            htf   = h["tempF"]
            chance_rain = h.get("chanceofrain", "0")
            fcast.append(f"  {label}: {hdesc}, {htf}°F (rain {chance_rain}%)")

        lines = [
            f"LIVE BOSTON WEATHER (as of {datetime.now().strftime('%I:%M %p')}):",
            f"• Condition : {desc}",
            f"• Temperature: {temp_f}°F / {temp_c}°C  (feels like {feels_f}°F)",
            f"• Humidity   : {humidity}%   Wind: {wind_mph} mph   Visibility: {vis_mi} mi",
            "• Hourly forecast:",
            *fcast,
        ]
        card = {"desc": desc, "temp_f": temp_f, "temp_c": temp_c,
                "feels_f": feels_f, "humidity": humidity, "wind_mph": wind_mph}
        return "\n".join(lines), card
    except Exception as e:
        logging.warning(f"Weather error: {e}")
        return "Weather data currently unavailable.", {}


def _fetch_dining():
    """Dining hall hours from nudining.com."""
    try:
        r    = req_lib.get("https://nudining.com/public/hours-of-operation",
                           headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, "lxml")
        lines = [f"NEU DINING HOURS (as of {datetime.now().strftime('%I:%M %p')}):\n"]
        cards = []
        # Generic extraction: grab headings and associated time text
        for tag in soup.find_all(["h2", "h3", "h4"]):
            name = tag.get_text(strip=True)
            if not name or len(name) > 80:
                continue
            sibling = tag.find_next_sibling()
            hours   = sibling.get_text(" ", strip=True)[:200] if sibling else ""
            if hours:
                lines.append(f"• {name}: {hours}")
                cards.append({"name": name, "hours": hours})
        if len(cards) == 0:
            # Fallback: just dump readable text
            for p in soup.find_all("p")[:20]:
                t = p.get_text(" ", strip=True)
                if t: lines.append(f"  {t}")
        return "\n".join(lines), cards
    except Exception as e:
        logging.warning(f"Dining error: {e}")
        return "Dining hours currently unavailable.", []


def fetch_live_parking(): return _cached("parking", CACHE_TTL, _fetch_parking)
def fetch_live_events():  return _cached("events",  CACHE_TTL, _fetch_events)
def fetch_live_news():    return _cached("news",    CACHE_TTL, _fetch_news)
def fetch_live_weather(): return _cached("weather", CACHE_TTL, _fetch_weather)
def fetch_live_dining():  return _cached("dining",  600,       _fetch_dining)   # 10-min cache

# ─── Canvas LMS ───────────────────────────────────────────────────────────────

CANVAS_CACHE: dict = {}   # {user_id: {"data": ..., "ts": datetime}}
CANVAS_TTL   = 300        # 5-min cache per user

CANVAS_KW = re.compile(
    r"\b(assignment|quiz|exam|midterm|final|due|deadline|submission|canvas|"
    r"course|class|grade|discussion|announcement|module|homework|hw|project|"
    r"essay|presentation|lab|report)\b", re.I)


def _canvas_headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _canvas_get(base_url, token, endpoint, params=None):
    url = f"{base_url}/api/v1{endpoint}"
    r   = req_lib.get(url, headers=_canvas_headers(token),
                      params=params, timeout=12)
    r.raise_for_status()
    return r.json()


def compute_urgency(due_at_str):
    if not due_at_str:
        return "low"
    try:
        due = datetime.fromisoformat(due_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff_h = (due - now).total_seconds() / 3600
        if diff_h < 0:       return "overdue"
        elif diff_h <= 24:   return "critical"
        elif diff_h <= 48:   return "high"
        elif diff_h <= 168:  return "medium"
        else:                return "low"
    except Exception:
        return "low"


def fmt_due(due_at_str):
    if not due_at_str:
        return "No due date"
    try:
        dt = datetime.fromisoformat(due_at_str.replace("Z", "+00:00"))
        return dt.strftime("%a %b %d · %I:%M %p")
    except Exception:
        return due_at_str


def fetch_canvas_data(user_id):
    """Fetch all Canvas academic data for a user. Returns list of item dicts."""
    cfg = DB.get_canvas_config(user_id)
    if not cfg:
        return None, "Canvas not connected"

    # Check cache
    cached = CANVAS_CACHE.get(user_id)
    if cached and (datetime.now() - cached["ts"]).seconds < CANVAS_TTL:
        return cached["data"], None

    base  = cfg["canvas_url"]
    token = cfg["canvas_token"]
    items = []

    try:
        # 1. Active courses
        courses = _canvas_get(base, token, "/courses", {
            "enrollment_state": "active", "per_page": 50,
            "include[]": ["term"]
        })
        if isinstance(courses, dict):   # error response
            return None, courses.get("errors", [{}])[0].get("message", "Canvas error")

        course_map = {c["id"]: c.get("name", f"Course {c['id']}") for c in courses}

        for course in courses:
            cid   = course["id"]
            cname = course.get("name", f"Course {cid}")

            # 2. Assignments
            try:
                asgns = _canvas_get(base, token, f"/courses/{cid}/assignments", {
                    "per_page": 50, "order_by": "due_at",
                    "bucket": "future"
                })
                for a in (asgns if isinstance(asgns, list) else []):
                    items.append({
                        "id":      f"asgn_{a['id']}",
                        "type":    "assignment",
                        "title":   a.get("name", "Untitled"),
                        "course":  cname,
                        "due_at":  a.get("due_at"),
                        "due_fmt": fmt_due(a.get("due_at")),
                        "urgency": compute_urgency(a.get("due_at")),
                        "url":     a.get("html_url", ""),
                        "points":  a.get("points_possible"),
                        "submitted": a.get("has_submitted_submissions", False),
                    })
            except Exception:
                pass

            # 3. Quizzes
            try:
                quizzes = _canvas_get(base, token, f"/courses/{cid}/quizzes", {"per_page": 50})
                for q in (quizzes if isinstance(quizzes, list) else []):
                    items.append({
                        "id":      f"quiz_{q['id']}",
                        "type":    "quiz",
                        "title":   q.get("title", "Untitled Quiz"),
                        "course":  cname,
                        "due_at":  q.get("due_at"),
                        "due_fmt": fmt_due(q.get("due_at")),
                        "urgency": compute_urgency(q.get("due_at")),
                        "url":     q.get("html_url", ""),
                        "points":  q.get("points_possible"),
                        "time_limit": q.get("time_limit"),
                    })
            except Exception:
                pass

            # 4. Announcements
            try:
                ann = _canvas_get(base, token, f"/courses/{cid}/discussion_topics", {
                    "per_page": 20, "only_announcements": True
                })
                for a in (ann if isinstance(ann, list) else [])[:5]:
                    items.append({
                        "id":      f"ann_{a['id']}",
                        "type":    "announcement",
                        "title":   a.get("title", "Announcement"),
                        "course":  cname,
                        "due_at":  None,
                        "due_fmt": fmt_due(a.get("posted_at")),
                        "urgency": "low",
                        "url":     a.get("html_url", ""),
                        "message": a.get("message", "")[:300],
                    })
            except Exception:
                pass

        # Sort: overdue first, then by urgency, then by due_at
        urgency_order = {"overdue": 0, "critical": 1, "high": 2, "medium": 3, "low": 4}
        items.sort(key=lambda x: (
            urgency_order.get(x["urgency"], 5),
            x["due_at"] or "9999"
        ))

        CANVAS_CACHE[user_id] = {"data": items, "ts": datetime.now()}
        return items, None

    except req_lib.exceptions.HTTPError as e:
        msg = f"Canvas API error: {e.response.status_code}"
        logging.warning(msg)
        return None, msg
    except Exception as e:
        logging.warning(f"Canvas fetch error: {e}")
        return None, str(e)


def build_canvas_context(items):
    """Format Canvas items as a readable context block for the LLM."""
    if not items:
        return "No upcoming Canvas items found."
    lines = ["CANVAS ACADEMIC DATA (real-time from Canvas LMS):\n"]
    urgent = [i for i in items if i["urgency"] in ("overdue", "critical", "high")]
    upcoming = [i for i in items if i["urgency"] in ("medium", "low")]

    if urgent:
        lines.append("⚠️  URGENT ITEMS:")
        for i in urgent:
            badge = "🔴 OVERDUE" if i["urgency"] == "overdue" else ("🔴 DUE TODAY" if i["urgency"] == "critical" else "🟠 DUE SOON")
            lines.append(f"  • [{i['type'].upper()}] {i['title']} — {i['course']} | {badge} | {i['due_fmt']}")
    if upcoming:
        lines.append("\n📋 UPCOMING:")
        for i in upcoming[:10]:
            emoji = "🟡" if i["urgency"] == "medium" else "🟢"
            lines.append(f"  • [{i['type'].upper()}] {i['title']} — {i['course']} | {emoji} {i['due_fmt']}")
    return "\n".join(lines)


# ─── WhatsApp (Twilio) ────────────────────────────────────────────────────────

def send_whatsapp(to_phone: str, message: str) -> tuple[bool, str]:
    """Send a WhatsApp message via Twilio. Returns (success, sid_or_error)."""
    sid   = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_ = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not sid or not token:
        return False, "Twilio credentials not configured"

    phone_to = to_phone.strip()
    if not phone_to.startswith("whatsapp:"):
        phone_to = f"whatsapp:{phone_to}"

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(body=message, from_=from_, to=phone_to)
        return True, msg.sid
    except Exception as e:
        logging.error(f"WhatsApp send error: {e}")
        return False, str(e)


def whatsapp_reminder_text(item: dict) -> str:
    """Format a Canvas item as a concise WhatsApp reminder."""
    urgency_label = {
        "overdue":  "⚠️ OVERDUE",
        "critical": "🔴 Due TODAY",
        "high":     "🟠 Due SOON (< 48h)",
        "medium":   "🟡 Due this week",
        "low":      "🟢 Upcoming",
    }.get(item.get("urgency", "low"), "📌")

    return (
        f"📚 *NEU Assistant Reminder*\n"
        f"{urgency_label}: *{item['title']}*\n"
        f"Course: {item.get('course','')}\n"
        f"Type: {item.get('type','').title()}\n"
        f"Due: {item.get('due_fmt','N/A')}\n"
        f"Open: {item.get('url','canvas.northeastern.edu')}"
    )

# ─── RAG ──────────────────────────────────────────────────────────────────────

def retrieve(query):
    query_vec = embed_query(query)
    results = pinecone_query(query_vec, TOP_K)
    chunks = []
    for match in results.get("matches", []):
        score = match.get("score", 0)
        if score < 0.25:
            continue
        meta = match.get("metadata", {})
        chunks.append({
            "text": meta.get("text", ""),
            "meta": {"title": meta.get("title", ""), "url": meta.get("url", "")},
            "dist": 1 - score,
        })
    return chunks


def build_context(chunks):
    if not chunks:
        return "No relevant knowledge base entries found."
    parts = []
    for i, c in enumerate(chunks, 1):
        title = c["meta"].get("title", "")
        url   = c["meta"].get("url", "")
        parts.append(
            f"[Source {i}]"
            + (f" {title}" if title else "")
            + (f"\nURL: {url}" if url else "")
            + f"\n{c['text'].strip()}"
        )
    return "\n\n---\n\n".join(parts)


def generate_title(query):
    """Ask the LLM to produce a short conversation title (≤6 words)."""
    try:
        r = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content":
                    "You create short, descriptive conversation titles. "
                    "Respond with ONLY the title — max 6 words, title case, no punctuation."},
                {"role": "user", "content": f"First message: {query}"}
            ],
            max_tokens=20,
            temperature=0.3,
        )
        return r.choices[0].message.content.strip()[:60]
    except Exception:
        return query[:60]


def ask(query, history, user_id=None):
    chunks  = retrieve(query)
    context = build_context(chunks)

    # Live campus data
    live_sections = []
    if WEATHER_KW.search(query):
        txt, _ = fetch_live_weather()
        live_sections.append(f"=== LIVE BOSTON WEATHER ===\n{txt}\n=== END ===")
    if PARKING_KW.search(query):
        txt, _ = fetch_live_parking()
        live_sections.append(f"=== LIVE PARKING ===\n{txt}\n=== END ===")
    if EVENTS_KW.search(query):
        txt, _ = fetch_live_events()
        live_sections.append(f"=== LIVE CAMPUS EVENTS ===\n{txt}\n=== END ===")
    if NEWS_KW.search(query):
        txt, _ = fetch_live_news()
        live_sections.append(f"=== LIVE CAMPUS NEWS ===\n{txt}\n=== END ===")
    if DINING_KW.search(query):
        txt, _ = fetch_live_dining()
        live_sections.append(f"=== DINING HOURS ===\n{txt}\n=== END ===")

    # Canvas academic data — inject whenever query looks academic OR always if user has Canvas
    canvas_block = ""
    if user_id:
        canvas_items, canvas_err = fetch_canvas_data(user_id)
        if canvas_items is not None and (CANVAS_KW.search(query) or len(canvas_items) > 0):
            canvas_block = f"\n\n=== CANVAS ACADEMIC DATA ===\n{build_canvas_context(canvas_items)}\n=== END ==="
        elif canvas_err == "Canvas not connected" and CANVAS_KW.search(query):
            canvas_block = "\n\n=== CANVAS STATUS ===\nCanvas LMS is not connected for this user.\n=== END ==="

    live_block = ("\n\n" + "\n\n".join(live_sections)) if live_sections else ""

    user_msg = (
        f"## Knowledge Base\n\n{context}"
        f"{canvas_block}"
        f"{live_block}"
        f"\n\n---\n\n**Question:** {query}"
    )

    trimmed_history = history[-(MAX_HISTORY):]

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + trimmed_history
        + [{"role": "user", "content": user_msg}]
    )

    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=2048,
        temperature=0.3,
        top_p=0.9,
    )
    return response.choices[0].message.content


# ─── Auth routes ──────────────────────────────────────────────────────────────

@app.route("/login")
def login_page():
    return _serve_react()

@app.route("/api/auth/providers")
def auth_providers():
    """Return which OAuth providers are configured."""
    def _ok(key, placeholder):
        val = os.getenv(key, "")
        return bool(val) and val != placeholder
    return jsonify({
        "google":    _ok("GOOGLE_CLIENT_ID",    "your-google-client-id.apps.googleusercontent.com"),
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/auth/<provider>")
def auth_login(provider):
    client   = oauth.create_client(provider)
    # Build redirect URI explicitly for Vercel HTTPS
    # Always use the same host the user is currently on (cookie domain must match)
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else request.scheme
    redirect_uri = f"{scheme}://{request.host}/auth/{provider}/callback"
    return client.authorize_redirect(redirect_uri)


@app.route("/auth/<provider>/callback")
def auth_callback(provider):
    try:
        client = oauth.create_client(provider)
        token  = client.authorize_access_token()

        if provider == "google":
            info   = token.get("userinfo") or client.userinfo()
            uid    = f"google_{info['sub']}"
            name   = info.get("name", "User")
            email  = info.get("email", "")
            avatar = info.get("picture", "")

        else:
            return redirect("/login?error=unsupported_provider")

        user = DB.upsert_user(uid, name, email, avatar, provider)
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        session["user_email"]= user["email"]
        session["user_avatar"]= user.get("avatar","")
        session.permanent    = True
        return redirect("/app")

    except Exception as e:
        logging.error(f"Auth error ({provider}): {e}")
        return redirect("/login?error=auth_failed")


# ─── User info API ───────────────────────────────────────────────────────────

@app.route("/api/me")
def api_me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "not authenticated"}), 401
    return jsonify({
        "id":     uid,
        "name":   session.get("user_name", ""),
        "email":  session.get("user_email", ""),
        "avatar": session.get("user_avatar", ""),
    })


@app.route("/api/debug")
def api_debug():
    """Diagnostic endpoint — check all services."""
    results = {"session": bool(session.get("user_id")), "env": {}}
    for key in ["GROQ_API_KEY", "PINECONE_API_KEY", "PINECONE_HOST", "PINECONE_INDEX", "HF_TOKEN", "FLASK_SECRET"]:
        val = os.getenv(key, "")
        results["env"][key] = f"{val[:6]}..." if val else "MISSING"
    # Test HF
    try:
        r = req_lib.post(
            f"https://router.huggingface.co/hf-inference/models/{HF_EMBED_MODEL}",
            json={"inputs": "test"}, headers={"Authorization": f"Bearer {HF_TOKEN}"}, timeout=10)
        results["hf"] = {"status": r.status_code, "dim": len(r.json()) if r.ok else r.text[:100]}
    except Exception as e:
        results["hf"] = {"error": str(e)}
    # Test Pinecone
    try:
        host = _pinecone_host()
        r = req_lib.get(f"{host}/describe_index_stats", headers={"Api-Key": PINECONE_API_KEY}, timeout=10)
        results["pinecone"] = {"status": r.status_code, "vectors": r.json().get("totalVectorCount") if r.ok else r.text[:100]}
    except Exception as e:
        results["pinecone"] = {"error": str(e)}
    return jsonify(results)


# ─── Serve React SPA ────────────────────────────────────────────────────────

def _serve_react():
    """Serve React index.html for SPA routing."""
    index = os.path.join(REACT_BUILD, "index.html")
    if os.path.exists(index):
        return send_from_directory(REACT_BUILD, "index.html")
    return "React build not found. Run: cd frontend && npm run build", 404

@app.route("/")
def landing():
    return _serve_react()

@app.route("/app")
def chat_app():
    return _serve_react()


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    data    = request.get_json()
    query   = data.get("message","").strip()
    conv_id = data.get("conversation_id")

    if not query:
        return jsonify({"error": "Empty message"}), 400

    user_id = session["user_id"]

    # Create new conversation if needed
    if not conv_id:
        conv_id = str(uuid.uuid4())
        title   = query[:60]
        DB.create_conversation(conv_id, user_id, title)
    else:
        DB.touch_conversation(conv_id)

    # Build history from DB (roles are already "user" / "assistant")
    saved_msgs = DB.get_messages(conv_id)
    history    = [{"role": m["role"], "content": m["content"]} for m in saved_msgs]

    try:
        answer = ask(query, history, user_id=session.get("user_id"))
    except Exception as e:
        logging.error(f"ask() error: {e}")
        return jsonify({"error": str(e)}), 500

    # Persist both messages
    DB.save_message(conv_id, "user",      query)
    DB.save_message(conv_id, "assistant", answer)

    # Generate a proper title after the first exchange
    if len(saved_msgs) == 0:
        title = generate_title(query)
        DB.update_conversation_title(conv_id, title)

    return jsonify({"answer": answer, "conversation_id": conv_id})


@app.route("/api/conversations")
@login_required
def list_conversations():
    convs = DB.get_conversations(session["user_id"])
    return jsonify(convs)


@app.route("/api/conversations/<conv_id>")
@login_required
def get_conversation(conv_id):
    msgs = DB.get_messages(conv_id)
    return jsonify({"messages": msgs})


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
@login_required
def delete_conversation(conv_id):
    DB.delete_conversation(conv_id, session["user_id"])
    return jsonify({"status": "deleted"})


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    # Just signal new chat — no server state to clear (history is per-conversation)
    return jsonify({"status": "ok"})


_DEFAULT_IDX_STATE = {"status": "disabled", "last_run": None, "pages_indexed": 0, "chunks_upserted": 0, "error": None}

@app.route("/api/live-feed")
@login_required
def live_feed():
    _, events  = fetch_live_events()
    _, news    = fetch_live_news()
    _, parking = fetch_live_parking()
    idx = _indexer.state if _indexer else _DEFAULT_IDX_STATE
    return jsonify({
        "events":  events[:10],
        "news":    news[:8],
        "parking": parking,
        "ts":      datetime.now().strftime("%I:%M %p"),
        "index": {
            "status":          idx["status"],
            "last_run":        idx["last_run"].isoformat() if idx.get("last_run") else None,
            "pages_indexed":   idx.get("pages_indexed", 0),
            "chunks_upserted": idx.get("chunks_upserted", 0),
        }
    })


@app.route("/api/index/status")
@login_required
def index_status():
    idx = _indexer.state if _indexer else _DEFAULT_IDX_STATE
    return jsonify({
        "status":          idx["status"],
        "last_run":        idx["last_run"].isoformat() if idx.get("last_run") else None,
        "pages_indexed":   idx.get("pages_indexed", 0),
        "chunks_upserted": idx.get("chunks_upserted", 0),
        "error":           idx.get("error"),
        "total_chunks":    pinecone_stats().get("totalVectorCount", 0),
    })


@app.route("/api/index/refresh", methods=["POST"])
@login_required
def index_refresh():
    if not _indexer:
        return jsonify({"error": "Indexer not available in serverless mode"}), 400
    if _indexer.state["status"] == "running":
        return jsonify({"error": "Indexer already running"}), 409
    import threading
    threading.Thread(target=_indexer.run_once, daemon=True, name="live-indexer-manual").start()
    return jsonify({"ok": True, "message": "Re-index started in background"})


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    return _serve_react()


# ─── Canvas API routes ────────────────────────────────────────────────────────

@app.route("/api/canvas/status")
@login_required
def canvas_status():
    cfg = DB.get_canvas_config(session["user_id"])
    return jsonify({"connected": bool(cfg),
                    "canvas_url": cfg["canvas_url"] if cfg else None})


@app.route("/api/canvas/connect", methods=["POST"])
@login_required
def canvas_connect():
    data         = request.get_json()
    canvas_url   = (data.get("canvas_url") or "").strip().rstrip("/")
    canvas_token = (data.get("canvas_token") or "").strip()
    if not canvas_url or not canvas_token:
        return jsonify({"error": "canvas_url and canvas_token are required"}), 400

    # Verify credentials by calling /api/v1/users/self
    try:
        r = req_lib.get(f"{canvas_url}/api/v1/users/self",
                        headers=_canvas_headers(canvas_token), timeout=10)
        if r.status_code == 401:
            return jsonify({"error": "Invalid Canvas token — please check and try again"}), 401
        r.raise_for_status()
        profile = r.json()
    except req_lib.exceptions.RequestException as e:
        return jsonify({"error": f"Could not reach Canvas: {e}"}), 400

    DB.save_canvas_config(session["user_id"], canvas_url, canvas_token)
    CANVAS_CACHE.pop(session["user_id"], None)   # clear stale cache
    return jsonify({"ok": True, "name": profile.get("name", "")})


@app.route("/api/canvas/disconnect", methods=["POST"])
@login_required
def canvas_disconnect():
    DB.delete_canvas_config(session["user_id"])
    CANVAS_CACHE.pop(session["user_id"], None)
    return jsonify({"ok": True})


@app.route("/api/canvas/data")
@login_required
def canvas_data():
    items, err = fetch_canvas_data(session["user_id"])
    if err:
        return jsonify({"error": err}), 400 if err == "Canvas not connected" else 502
    return jsonify({"items": items, "ts": datetime.now().strftime("%I:%M %p")})


@app.route("/api/canvas/refresh", methods=["POST"])
@login_required
def canvas_refresh():
    CANVAS_CACHE.pop(session["user_id"], None)
    items, err = fetch_canvas_data(session["user_id"])
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"items": items, "ts": datetime.now().strftime("%I:%M %p")})


# ─── WhatsApp API routes ──────────────────────────────────────────────────────

@app.route("/api/whatsapp/status")
@login_required
def whatsapp_status():
    cfg = DB.get_whatsapp_config(session["user_id"])
    return jsonify({"configured": bool(cfg),
                    "phone":    cfg["phone"]   if cfg else None,
                    "enabled":  bool(cfg["enabled"]) if cfg else False})


@app.route("/api/whatsapp/configure", methods=["POST"])
@login_required
def whatsapp_configure():
    data    = request.get_json()
    phone   = (data.get("phone") or "").strip()
    enabled = data.get("enabled", True)
    if not phone:
        return jsonify({"error": "phone is required"}), 400
    DB.save_whatsapp_config(session["user_id"], phone, enabled)
    return jsonify({"ok": True})


@app.route("/api/whatsapp/test", methods=["POST"])
@login_required
def whatsapp_test():
    cfg = DB.get_whatsapp_config(session["user_id"])
    if not cfg:
        return jsonify({"error": "WhatsApp not configured"}), 400
    ok, result = send_whatsapp(cfg["phone"],
        "👋 *NEU Assistant*\nYour WhatsApp notifications are now active! "
        "You'll receive reminders for upcoming assignments, quizzes, and deadlines.")
    return jsonify({"ok": ok, "result": result})


@app.route("/api/whatsapp/send-reminder", methods=["POST"])
@login_required
def whatsapp_send_reminder():
    data        = request.get_json()
    reminder_id = data.get("reminder_id")
    if not reminder_id:
        return jsonify({"error": "reminder_id required"}), 400

    cfg = DB.get_whatsapp_config(session["user_id"])
    if not cfg or not cfg["enabled"]:
        return jsonify({"error": "WhatsApp not configured or disabled"}), 400

    reminders = DB.get_reminders(session["user_id"])
    item = next((r for r in reminders if r["id"] == reminder_id), None)
    if not item:
        return jsonify({"error": "Reminder not found"}), 404

    msg  = whatsapp_reminder_text(item)
    ok, result = send_whatsapp(cfg["phone"], msg)
    if ok:
        DB.mark_whatsapp_sent(reminder_id)
    return jsonify({"ok": ok, "result": result})


# ─── Reminders API routes ─────────────────────────────────────────────────────

@app.route("/api/reminders")
@login_required
def list_reminders():
    items = DB.get_reminders(session["user_id"])
    return jsonify(items)


@app.route("/api/reminders", methods=["POST"])
@login_required
def create_reminder():
    data = request.get_json()
    rid  = DB.save_reminder(
        uid       = session["user_id"],
        item_id   = data.get("item_id", str(uuid.uuid4())),
        item_type = data.get("item_type", "custom"),
        title     = data.get("title", "Reminder"),
        course    = data.get("course"),
        due_at    = data.get("due_at"),
        urgency   = data.get("urgency", compute_urgency(data.get("due_at"))),
    )
    # Auto-send WhatsApp if critical and user has WA configured
    urgency = data.get("urgency", "low")
    if urgency in ("critical", "high"):
        cfg = DB.get_whatsapp_config(session["user_id"])
        if cfg and cfg["enabled"]:
            msg = whatsapp_reminder_text({**data, "id": rid})
            ok, _ = send_whatsapp(cfg["phone"], msg)
            if ok:
                DB.mark_whatsapp_sent(rid)
    return jsonify({"id": rid})


@app.route("/api/reminders/<rid>", methods=["DELETE"])
@login_required
def delete_reminder_route(rid):
    DB.delete_reminder(rid, session["user_id"])
    return jsonify({"ok": True})


@app.route("/api/reminders/<rid>/dismiss", methods=["POST"])
@login_required
def dismiss_reminder_route(rid):
    DB.dismiss_reminder(rid, session["user_id"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=False, port=8080)
