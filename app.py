"""
TerpWell,UMD Wellness Companion
Clean mobile-first redesign with two-layer AI governance.
"""

import os, json, time, re, random, datetime
import streamlit as st
import anthropic
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

JOURNAL_PROMPTS = [
    "What's one thing that went well today, even if it was small?",
    "Describe how you're feeling right now using three words.",
    "What's been weighing on your mind lately? Try to put it into words.",
    "What would make tomorrow a little better than today?",
    "Who is someone you can reach out to when things feel hard?",
    "What's something you're grateful for, even in the middle of difficulty?",
    "If a friend told you they were feeling what you're feeling, what would you say to them?",
    "What's one small thing you can do in the next hour to take care of yourself?",
    "What does 'feeling okay' look like for you? Describe it.",
    "What's one boundary you wish you could set, and what's stopping you?",
]

GROUNDING_STEPS = [
    ("5 things you can SEE", "Look around and name 5 things you can see right now."),
    ("4 things you can TOUCH", "Notice 4 things you can physically feel, like the chair, your feet on the floor."),
    ("3 things you can HEAR", "Listen carefully. What 3 sounds can you hear?"),
    ("2 things you can SMELL", "Notice 2 scents around you, even subtle ones."),
    ("1 thing you can TASTE", "What is one thing you can taste right now?"),
]

# ── DATABASE ───────────────────────────────────────────────────────────────────

DB_PATH = Path("/home/sujeet/terpwell/terpwell.db")

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS mood_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood TEXT NOT NULL,
            mood_score INTEGER NOT NULL,
            note TEXT DEFAULT '',
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            audit_json TEXT DEFAULT '{}',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

def seed_test_user():
    """Create test user with 30 days of realistic mood data."""
    conn = get_db()

    # Check if test user exists
    existing = conn.execute("SELECT id FROM users WHERE username = 'testterp'").fetchone()
    if existing:
        conn.close()
        return

    # Create test user
    conn.execute("INSERT INTO users (username, password, display_name) VALUES ('testterp', 'terp2026', 'Testudo Terp')")
    user_id = conn.execute("SELECT id FROM users WHERE username = 'testterp'").fetchone()[0]

    # Seed 30 days of mood data with realistic college patterns
    import datetime as dt
    now = dt.datetime.now()

    # Realistic pattern: stressed during weekdays, better on weekends, dip during midterms
    mood_map = {"😢": 1, "😟": 2, "😐": 3, "🙂": 4, "😊": 5}
    moods = list(mood_map.keys())

    notes = {
        1: ["feeling overwhelmed", "couldn't sleep", "had a panic attack before class", "everything feels like too much"],
        2: ["stressed about homework", "didn't eat well today", "skipped class", "feeling behind in CMSC"],
        3: ["okay day", "went through the motions", "meh", "nothing special"],
        4: ["good study session at McKeldin", "hung out with friends at Stamp", "nice walk by Lake Artemesia", "productive day"],
        5: ["great day! aced my quiz", "beautiful day on the mall", "fun RecWell climbing session", "laughed a lot with roommates"],
    }

    for day_offset in range(30, 0, -1):
        date = now - dt.timedelta(days=day_offset)
        weekday = date.weekday()  # 0=Mon, 6=Sun

        # Base mood: weekdays lower, weekends higher
        if weekday < 5:  # weekday
            base = random.choices([1, 2, 3, 4, 5], weights=[5, 15, 40, 30, 10])[0]
        else:  # weekend
            base = random.choices([1, 2, 3, 4, 5], weights=[2, 8, 25, 40, 25])[0]

        # Midterm dip (days 10-15 ago)
        if 10 <= day_offset <= 15:
            base = max(1, base - 1)

        # Recovery after midterms (days 5-9 ago)
        if 5 <= day_offset <= 9:
            base = min(5, base + 1)

        # 1-3 entries per day
        num_entries = random.choices([1, 2, 3], weights=[40, 40, 20])[0]

        for entry_idx in range(num_entries):
            # Slight variation per entry
            score = max(1, min(5, base + random.randint(-1, 1)))
            emoji = moods[score - 1]
            note = random.choice(notes[score]) if random.random() > 0.3 else ""

            # Random time during the day
            hour = random.randint(7, 23)
            minute = random.randint(0, 59)
            entry_time = date.replace(hour=hour, minute=minute, second=0)

            conn.execute(
                "INSERT INTO mood_entries (user_id, mood, mood_score, note, logged_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, emoji, score, note, entry_time.strftime("%Y-%m-%d %H:%M:%S"))
            )

    conn.commit()
    conn.close()

# DB helper functions
def authenticate(username, password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    return dict(user) if user else None

def log_mood_db(user_id, mood, mood_score, note=""):
    conn = get_db()
    conn.execute("INSERT INTO mood_entries (user_id, mood, mood_score, note) VALUES (?, ?, ?, ?)",
                 (user_id, mood, mood_score, note))
    conn.commit()
    conn.close()

def get_mood_history(user_id, days=30):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mood_entries WHERE user_id = ? AND logged_at >= datetime('now', ?) ORDER BY logged_at",
        (user_id, f"-{days} days")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_mood_summary(user_id, days=7):
    """Get mood stats for the last N days."""
    conn = get_db()
    rows = conn.execute(
        "SELECT mood_score, logged_at FROM mood_entries WHERE user_id = ? AND logged_at >= datetime('now', ?) ORDER BY logged_at",
        (user_id, f"-{days} days")
    ).fetchall()
    conn.close()
    if not rows:
        return {"avg": 0, "count": 0, "trend": "neutral", "entries": []}

    scores = [r["mood_score"] for r in rows]
    avg = sum(scores) / len(scores)

    # Trend: compare first half to second half
    mid = len(scores) // 2
    if mid > 0:
        first_half = sum(scores[:mid]) / mid
        second_half = sum(scores[mid:]) / (len(scores) - mid)
        if second_half - first_half > 0.5:
            trend = "improving"
        elif first_half - second_half > 0.5:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "neutral"

    return {"avg": avg, "count": len(scores), "trend": trend, "entries": [dict(r) for r in rows]}

def create_chat_session(user_id):
    conn = get_db()
    conn.execute("INSERT INTO chat_sessions (user_id) VALUES (?)", (user_id,))
    session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return session_id

def save_chat_message(session_id, user_id, role, content, audit_json="{}"):
    conn = get_db()
    conn.execute("INSERT INTO chat_messages (session_id, user_id, role, content, audit_json) VALUES (?, ?, ?, ?, ?)",
                 (session_id, user_id, role, content, audit_json))
    conn.commit()
    conn.close()

# Initialize DB and seed on startup
init_db()
seed_test_user()

# ── API SETUP ──────────────────────────────────────────────────────────────────

USE_BEDROCK = not os.environ.get("ANTHROPIC_API_KEY")
MODEL = "us.anthropic.claude-sonnet-4-6" if USE_BEDROCK else "claude-sonnet-4-6-20250514"

def get_client():
    if USE_BEDROCK:
        return anthropic.AnthropicBedrock(aws_region=os.environ.get("AWS_REGION", "us-east-1"))
    else:
        return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── CRISIS DETECTION ──────────────────────────────────────────────────────────

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "self-harm", "self harm",
    "want to die", "end it all", "end my life", "hurt myself",
    "no reason to live", "better off dead",
    "take my life", "don't want to be here", "can't go on",
]
CRISIS_PATTERN = re.compile("|".join(re.escape(k) for k in CRISIS_KEYWORDS), re.IGNORECASE)

def detect_crisis(text: str) -> bool:
    return bool(CRISIS_PATTERN.search(text))

def detect_crisis_claude(text: str) -> dict:
    """Claude-powered nuanced crisis classification,catches paraphrases regex misses."""
    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=80,
            system=(
                'You are a crisis detection classifier for a university wellness app. '
                'Classify the crisis level in the student message. '
                'Respond with JSON only, no other text: '
                '{"crisis_level": "none" | "mild" | "urgent", "reason": "one sentence"}'
            ),
            messages=[{"role": "user", "content": text}],
        )
        return json.loads(response.content[0].text.strip())
    except Exception:
        return {"crisis_level": "none", "reason": ""}

# ── TOPIC EXTRACTION ──────────────────────────────────────────────────────────

TOPIC_KEYWORDS = {
    "Exams": ["exam", "test", "midterm", "final", "grade", "grades", "gpa"],
    "Anxiety": ["anxious", "anxiety", "worried", "worry", "panic", "nervous"],
    "Stress": ["stress", "stressed", "overwhelmed", "pressure", "burnout"],
    "Loneliness": ["lonely", "alone", "isolated", "no friends", "disconnected"],
    "Homesickness": ["home", "miss my family", "homesick", "parents", "hometown"],
    "Imposter Syndrome": ["imposter", "don't belong", "not smart enough", "fake"],
    "Sleep": ["sleep", "insomnia", "tired", "exhausted", "can't sleep"],
    "Relationships": ["relationship", "breakup", "friend", "dating", "toxic"],
    "Academics": ["class", "professor", "assignment", "homework", "study"],
    "Self-Care": ["self-care", "exercise", "eating", "routine", "healthy"],
    "Crisis": ["crisis", "suicide", "self-harm", "hopeless", "helpless"],
}

def extract_topics(text: str) -> list:
    found = []
    tl = text.lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            found.append(topic)
    return found

# ── PROMPTS ───────────────────────────────────────────────────────────────────

def companion_prompt(mood, mood_context=""):
    return f"""You are TerpWell,think of yourself as a caring older student at the University of Maryland who's been through it all. You talk like a real person, not a chatbot. You use casual language, contractions, and you're genuinely warm. You're NOT a therapist, counselor, or medical professional,you're a supportive friend who happens to know every resource on campus.

## Your Personality:
- You speak naturally: "hey", "honestly", "I totally get that", "that sounds really rough"
- You share relatable observations: "midterm season at UMD is no joke" not "exam periods can be stressful"
- You're specific to UMD,you mention real places, real experiences, real campus life
- You ask thoughtful follow-up questions, don't just give advice
- You validate before suggesting,always acknowledge their feelings first
- One suggestion at a time, not a laundry list
- Keep it to 2-3 short paragraphs max

## UMD-Specific Knowledge:
When relevant, naturally weave in real UMD places and suggestions:

RELAXATION & NATURE:
- Lake Artemesia, peaceful walk, only 10 min from campus
- The Garden of Reflection near the Chapel. Quiet meditation spot
- Paint Branch Trail. Great for clearing your head with a run or walk
- McKeldin Mall, sit on the grass, people-watch, decompress between classes
- Clarice Smith Performing Arts Center. Free concerts and performances

FOOD & COMFORT:
- The Diner (open late). Comfort food when you need it at 1am
- Board & Brew on Route 1, chill board game cafe, great for socializing
- Vigilante Coffee in Hyattsville. Cozy off-campus study spot
- College Park farmers market (Saturdays). Nice way to get outside

SOCIAL & COMMUNITY:
- UMD RecWell, group fitness classes, rock climbing wall at Eppley
- Stamp Student Union, game room, events, just a good place to hang
- 400+ student orgs. There's literally a club for everything
- Intramural sports. Low-pressure way to move your body and meet people
- Terrapin Trail Club. Hiking trips to get off campus

ACADEMIC SUPPORT:
- Tutoring at the Learning Assistance Service in Shoemaker
- Writing Center in Tawes Hall. Help with papers
- Academic Success & Tutorial Services
- Each college has its own advising office

MINDFULNESS & WELLNESS:
- UMD RecWell offers free yoga and meditation classes
- Mindfulness Room in the Stamp Student Union
- Health Center has wellness workshops throughout the semester

NEURODIVERGENT SUPPORT:
- Accessibility & Disability Service (ADS): (301) 314-7682, ads.umd.edu. ADHD, learning disabilities, autism support, free for registered students
- ADHD/LD Coaching: through ADS, free for registered students, ads.umd.edu/services/coaching
- If you're struggling in class and think ADHD or a learning difference might be involved, ADS is genuinely helpful and low-barrier to access

## Crisis Protocol:
If the user mentions suicide, self-harm, wanting to die, or immediate danger, drop everything and respond with empathy + these exact resources:
"I'm really glad you told me this. You don't have to go through this alone. Please reach out right now:
- **988 Suicide & Crisis Lifeline**: Call or text 988 (24/7, free)
- **UMD CAPS Crisis Line**: (301) 314-7651 (press 1 after hours)
- **Crisis Text Line**,Text HOME to 741741
These are real people who care and are trained to help. Can I help you take that step?"

## Verified UMD Resources (use ONLY these,never make up resources):
- UMD Counseling Center (CAPS): (301) 314-7651, Shoemaker Building, 1st floor
- CAPS after-hours crisis: (301) 314-7651, press 1
- UMD Health Center: (301) 314-8180, Campus Drive
- Campus Police emergency: 911 or (301) 405-3333
- CARE to Stop Violence: (301) 314-2222 (sexual assault, relationship violence)
- Dean of Students: (301) 314-8783 (academic concerns, personal emergencies)
- Resident Life 24/7 Duty Line: (301) 314-9237
- Accessibility & Disability Service (ADS): (301) 314-7682, ads.umd.edu
- ADHD/LD Coaching through ADS: ads.umd.edu/services/coaching

## Right Now:
Student's current mood: {mood}

## Student's Recent Mood Pattern:
{mood_context}
Use this context to personalize your response. If their mood has been declining, be extra gentle. If improving, acknowledge their progress.

## Rules:
- Be a human, not a helpline script
- Reference specific UMD places, not generic "go outside" or "try meditation"
- If someone mentions a specific situation (roommate issues, academic stress, loneliness), ask follow-up questions before jumping to solutions
- When suggesting professional help, normalize it: "tons of Terps use CAPS, it's literally free and right in Shoemaker"
- Never say "I'm just an AI" unprompted. Only clarify your limitations if directly asked or if the situation requires professional help
- Use the student's mood context naturally, don't announce it"""

def governance_prompt():
    return """You are the TerpWell Governance Auditor. Review this AI wellness companion response for safety and accuracy.

## Checks:
1. CRISIS_DETECTION: If user mentions suicide/self-harm, response MUST include 988, CAPS (301) 314-7651, and Crisis Text Line
2. NO_DIAGNOSIS: Response must NOT diagnose any mental health condition
3. NO_PRESCRIBING: Response must NOT recommend medication or specific clinical treatments
4. NO_MINIMIZING: Response must NOT dismiss or minimize feelings ("just think positive", "others have it worse")
5. RESOURCE_ACCURACY: All phone numbers must be correct: CAPS=(301)314-7651, Health Center=(301)314-8180, Police=(301)405-3333, CARE=(301)314-2222, Dean=(301)314-8783, ADS=(301)314-7682
6. NO_HALLUCINATION: No fake organizations, hotlines, buildings, or UMD resources. Only reference real places.
7. EMPATHETIC_TONE: Must be warm, human, and validating, not robotic or clinical

Respond ONLY with this JSON (no other text):
{"approved": true/false, "score": 0-100, "checks": {"crisis_detection": {"pass": true/false, "note": "..."}, "no_diagnosis": {"pass": true/false, "note": "..."}, "no_prescribing": {"pass": true/false, "note": "..."}, "no_minimizing": {"pass": true/false, "note": "..."}, "resource_accuracy": {"pass": true/false, "note": "..."}, "no_hallucination": {"pass": true/false, "note": "..."}, "empathetic_tone": {"pass": true/false, "note": "..."}}, "corrections": "...", "corrected_response": "..."}"""

def parse_governance_json(raw):
    try:
        return json.loads(raw)
    except:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return {"approved": True, "score": 75, "checks": {}, "corrections": "Parse error", "corrected_response": ""}

# ── BACKEND FUNCTIONS ─────────────────────────────────────────────────────────

def stream_companion(user_message: str, mood: str, history: list, placeholder) -> str:
    """Stream companion response token-by-token into a Streamlit placeholder."""
    client = get_client()
    messages_payload = history + [{"role": "user", "content": user_message}]
    full_text = ""

    # Build mood context
    if st.session_state.get("user"):
        summary = get_mood_summary(st.session_state.user["id"], days=7)
        mood_context = f"Last 7 days: {summary['count']} entries, avg {summary['avg']:.1f}/5, trend: {summary['trend']}"
    else:
        mood_context = ""

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=companion_prompt(mood, mood_context),
        messages=messages_payload,
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            placeholder.markdown(full_text + "▌")

    placeholder.markdown(full_text)
    return full_text


def run_governance(user_message: str, draft: str) -> tuple:
    """Run governance audit. Returns (audit_dict, was_corrected)."""
    client = get_client()
    gov_input = (
        f"USER MESSAGE:\n{user_message}\n\n"
        f"COMPANION RESPONSE:\n{draft}\n\n"
        f"Review this response."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=governance_prompt(),
        messages=[{"role": "user", "content": gov_input}],
    )
    audit = parse_governance_json(response.content[0].text)
    approved = audit.get("approved", True)
    if not approved:
        corrected = audit.get("corrected_response", "").strip()
        audit["_final"] = corrected if corrected else draft
    else:
        audit["_final"] = draft
    return audit, not approved


def export_session_markdown(
    messages: list,
    topics: list,
    mood: str,
    care_plan: dict | None,
    escalation_message: str | None,
    governance_scores: list,
    triage_level: str,
) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    avg_score = (
        f"{sum(governance_scores)/len(governance_scores):.0f}/100"
        if governance_scores else "—"
    )
    lines = [
        "# TerpWell Session Summary",
        f"**Date:** {now}",
        f"**Mood:** {mood or 'Not recorded'}",
        f"**Topics:** {', '.join(set(topics)) or 'None'}",
        f"**Avg. Governance Score:** {avg_score}",
        f"**Triage Level:** {triage_level}",
        "",
        "---",
        "",
        "## Conversation",
        "",
    ]
    for m in messages:
        role = "You" if m["role"] == "user" else "TerpWell"
        ts = m.get("timestamp", "")
        header = f"**{role}**" + (f" *({ts})*" if ts else "")
        lines += [header, "", m["content"], ""]

    if care_plan and care_plan.get("steps"):
        lines += ["---", "", "## Your Care Plan", ""]
        for i, step in enumerate(care_plan["steps"][:3], 1):
            lines += [
                f"**Step {i}: {step.get('action', '')}**",
                step.get("detail", ""),
                "",
            ]
        note = care_plan.get("note", "")
        if note:
            lines += [f"*{note}*", ""]

    if escalation_message:
        lines += [
            "---",
            "",
            "## Draft Outreach Message",
            "",
            escalation_message,
            "",
        ]

    lines += [
        "---",
        "",
        "## Crisis Resources",
        "- **988 Suicide & Crisis Lifeline:** Call or text 988 (24/7)",
        "- **UMD CAPS:** (301) 314-7651",
        "- **Crisis Text Line:** Text HOME to 741741",
        "- **UMD Health Center:** (301) 314-8180",
        "",
        "---",
        "*Generated by TerpWell,UMD Wellness Companion*  ",
        "*Not a substitute for professional mental health care.*",
    ]
    return "\n".join(lines)


def generate_escalation_message(messages: list, mood: str) -> str:
    client = get_client()
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages[-8:]
        if m["role"] in ("user", "assistant")
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=250,
        system=[{
            "type": "text",
            "text": (
                "You are helping a UMD student reach out for professional support. "
                "Based on their conversation, draft a brief message they can share with a counselor, RA, or trusted person. "
                "Write in first person as if the student is sending it. "
                "Summarize what they are going through without quoting them directly. "
                "End by asking for a conversation or appointment. "
                "Under 80 words. Warm, not clinical. No diagnosis language."
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Conversation context:\n{conversation}\n\n"
                f"Mood: {mood or 'Not specified'}\n\n"
                "Draft the outreach message."
            ),
        }],
    )
    return response.content[0].text.strip()


def generate_care_plan(messages: list, topics: list, mood: str) -> dict:
    client = get_client()
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages[-12:]
        if m["role"] in ("user", "assistant")
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=(
            "You are a wellness care coordinator for UMD students. "
            "Based on the conversation, produce a concise 3-step personal care plan. "
            "Be specific and warm. Reference real UMD resources where relevant. "
            'Return JSON only: {"steps": [{"action": "...", "detail": "..."}], "note": "..."}'
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Conversation:\n{conversation}\n\n"
                f"Topics: {', '.join(topics) or 'General wellness'}\n"
                f"Mood: {mood or 'Not specified'}\n\n"
                "Generate a 3-step personalized care plan."
            ),
        }],
    )
    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"steps": [], "note": raw}


# ── PLOTLY HELPERS ────────────────────────────────────────────────────────────

MOOD_COLORS = {1: "#ff453a", 2: "#ff9f0a", 3: "#ffd60a", 4: "#30d158", 5: "#34c759"}

def plotly_dark_theme():
    return dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888', family='Inter'),
        xaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a'),
        yaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a'),
        margin=dict(l=40, r=20, t=40, b=40),
    )


# ── PAGE CONFIG ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TerpWell",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── SESSION STATE ──────────────────────────────────────────────────────────────

defaults = {
    "messages": [],
    "mood": None,
    "crisis_detected": False,
    "pending_prompt": None,
    "show_resources": False,
    "topics": [],
    "triage_level": "none",
    "care_plan": None,
    "api_error": None,
    "governance_scores": [],
    "sentiment_scores": [],
    "escalation_message": None,
    "breathing_active": False,
    "breathing_phase": "in",
    "breathing_count": 0,
    "journal_prompt": None,
    "grounding_checks": [False] * 5,
    "show_grounding": False,
    "quick_prompt_selected": None,
    # Auth
    "logged_in": False,
    "user": None,
    "chat_session_id": None,
    # Navigation
    "screen": "login",  # "login", "chat", "mood_dashboard"
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── CSS ────────────────────────────────────────────────────────────────────────

st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif !important; }
.stApp { background: #0a0a0a !important; }

#MainMenu, footer, header, .stDeployButton { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

.main .block-container {
    padding: 0 1rem 100px 1rem !important;
    max-width: 720px !important;
}

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 10px;
    border-bottom: 1px solid #1a1a1a;
    margin-bottom: 16px;
}
.app-header-left { width: 44px; }
.app-header-center { text-align: center; flex: 1; }
.app-header-center h1 {
    font-size: 1rem;
    font-weight: 600;
    color: #fff;
    margin: 0;
    letter-spacing: -0.2px;
}
.app-header-center .subtitle {
    font-size: 0.72rem;
    color: #555;
    margin-top: 2px;
}
.resources-btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.15s;
    text-decoration: none;
}
.resources-btn:hover {
    background: #222;
    border-color: #ff453a;
}

/* Resources panel */
.resources-panel {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
}
.resources-panel-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.resource-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid #1a1a1a;
}
.resource-item:last-child { border-bottom: none; }
.resource-icon-box {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: #1a1a1a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    flex-shrink: 0;
}
.resource-icon-box.crisis { background: rgba(255,59,48,0.12); }
.resource-icon-box.counsel { background: rgba(10,132,255,0.12); }
.resource-icon-box.health { background: rgba(52,199,89,0.12); }
.resource-icon-box.safety { background: rgba(255,159,10,0.12); }
.resource-icon-box.access { background: rgba(139,92,246,0.12); }
.resource-info { flex: 1; min-width: 0; }
.resource-name { font-size: 0.85rem; font-weight: 500; color: #e5e5e7; }
.resource-phone { font-size: 0.82rem; color: #0a84ff; margin-top: 1px; }
.resource-desc { font-size: 0.72rem; color: #666; margin-top: 1px; }

.welcome-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 0 24px;
    text-align: center;
}
.welcome-icon { font-size: 3rem; margin-bottom: 16px; }
.welcome-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 6px;
}
.welcome-sub {
    font-size: 0.9rem;
    color: #666;
}

.msg-row-user {
    display: flex;
    justify-content: flex-end;
    margin: 6px 0;
}
.msg-bubble-user {
    background: #2c2c2e;
    color: #f5f5f7;
    padding: 12px 18px;
    border-radius: 20px 20px 6px 20px;
    max-width: 75%;
    font-size: 0.9rem;
    line-height: 1.55;
    word-wrap: break-word;
}

.msg-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    margin-top: 4px;
}

.gov-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.68rem;
    color: #4a4a4a;
    margin-top: 4px;
    padding: 2px 0;
}
.gov-tag.verified { color: #2d6a4f; }
.gov-tag.reviewed { color: #7c6a0a; }

.thinking {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 12px 0;
    padding-left: 8px;
}
.thinking-text {
    font-size: 0.82rem;
    color: #555;
}
.thinking-dots {
    display: inline-flex;
    gap: 3px;
}
.thinking-dots span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #555;
    animation: blink 1.4s infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
    0%, 80%, 100% { opacity: 0.3; }
    40% { opacity: 1; }
}

.crisis-card {
    background: #1a0505;
    border: 1px solid rgba(255,59,48,0.25);
    border-radius: 16px;
    padding: 20px;
    margin: 12px 0;
}
.crisis-title {
    font-weight: 600;
    color: #ff453a;
    font-size: 0.9rem;
    margin-bottom: 10px;
}
.crisis-body {
    color: #aaa;
    font-size: 0.85rem;
    line-height: 1.9;
}

.stChatInput > div { background: #0a0a0a !important; }
.stChatInput textarea, [data-testid="stChatInput"] textarea {
    background: #1a1a1a !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 24px !important;
    color: #f5f5f7 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 12px 20px !important;
}
.stChatInput textarea:focus, [data-testid="stChatInput"] textarea:focus {
    border-color: #3a3a3a !important;
    box-shadow: none !important;
}
.stChatInput button, [data-testid="stChatInput"] button {
    background: #fff !important;
    border-radius: 50% !important;
    color: #000 !important;
}

.stButton > button {
    background: #141414 !important;
    border: 1px solid #2a2a2a !important;
    color: #ccc !important;
    border-radius: 16px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
    padding: 12px 16px !important;
    text-align: left !important;
    transition: all 0.15s !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: #1c1c1c !important;
    border-color: #3a3a3a !important;
    color: #fff !important;
}
/* No special circular overrides,let all buttons use the default pill style */

[data-testid="stHorizontalBlock"] { gap: 8px !important; }

/* Override Streamlit markdown text color in chat */
.stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    color: #e5e5e7 !important;
}

.disclaimer {
    text-align: center;
    font-size: 0.68rem;
    color: #3a3a3a;
    padding: 12px 0;
    margin-top: 8px;
}

/* Login */
.login-container { max-width: 360px; margin: 80px auto 0; text-align: center; }
.login-logo { font-size: 3rem; margin-bottom: 12px; }
.login-title { font-size: 1.5rem; font-weight: 600; color: #fff; margin-bottom: 4px; }
.login-sub { font-size: 0.85rem; color: #666; margin-bottom: 32px; }
.login-hint { font-size: 0.72rem; color: #444; margin-top: 16px; }
.login-error { color: #ff453a; font-size: 0.82rem; margin-top: 8px; }

/* Stat cards */
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }
.stat-card {
    background: #141414;
    border: 1px solid #1e1e1e;
    border-radius: 14px;
    padding: 16px;
    text-align: center;
}
.stat-value { font-size: 1.5rem; font-weight: 700; color: #fff; }
.stat-label { font-size: 0.72rem; color: #666; margin-top: 4px; }
.stat-sub { font-size: 0.75rem; color: #888; margin-top: 2px; }

/* Dashboard nav */
.dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0 12px;
    border-bottom: 1px solid #1a1a1a;
    margin-bottom: 16px;
}
.dash-title { font-size: 1rem; font-weight: 600; color: #fff; }

/* Mood entry row */
.mood-entry-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #111;
}
.mood-entry-time { font-size: 0.75rem; color: #555; width: 80px; }
.mood-entry-emoji { font-size: 1.2rem; }
.mood-entry-note { font-size: 0.82rem; color: #999; }
</style>""")

# ── SCREEN RENDERERS ──────────────────────────────────────────────────────────

def render_login_screen():
    st.html("""<div class="login-container">
    <div class="login-logo">🐢</div>
    <div class="login-title">TerpWell</div>
    <div class="login-sub">Welcome back, Terp</div>
</div>""")

    username = st.text_input("Username", placeholder="Username", label_visibility="collapsed", key="login_username")
    password = st.text_input("Password", placeholder="Password", type="password", label_visibility="collapsed", key="login_password")

    if st.button("Log In", use_container_width=True, key="login_btn"):
        user = authenticate(username.strip(), password.strip())
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.session_state.screen = "chat"
            st.session_state.chat_session_id = create_chat_session(user["id"])
            st.rerun()
        else:
            st.html('<div class="login-error">Invalid username or password.</div>')

    st.html('<div class="login-hint">Demo: testterp / terp2026</div>')


def render_mood_dashboard():
    import html as html_mod
    import datetime as dt

    user = st.session_state.user

    # Header nav
    nav_left, nav_center, nav_right = st.columns([0.25, 0.5, 0.25], gap="small")
    with nav_left:
        if st.button("← Chat", key="dash_back", use_container_width=True):
            st.session_state.screen = "chat"
            st.rerun()
    with nav_center:
        st.html('<div class="dash-title" style="text-align:center;padding-top:8px;">Mood Dashboard</div>')
    with nav_right:
        if st.button("+ Log Mood", key="dash_log_btn", use_container_width=True):
            st.session_state["dash_show_log"] = not st.session_state.get("dash_show_log", False)
            st.rerun()

    st.html('<div style="border-bottom:1px solid #1a1a1a;margin-bottom:16px;"></div>')

    # Quick mood logger (toggleable)
    if st.session_state.get("dash_show_log", False):
        st.html('<div style="background:#111;border:1px solid #1e1e1e;border-radius:14px;padding:16px;margin-bottom:16px;">'
                '<div style="font-size:0.82rem;color:#888;margin-bottom:10px;">How are you feeling right now?</div></div>')
        mood_note_dash = st.text_input("Note (optional)", placeholder="What's going on?", key="dash_mood_note", label_visibility="collapsed")
        mood_emojis = ["😢", "😟", "😐", "🙂", "😊"]
        mood_scores = {"😢": 1, "😟": 2, "😐": 3, "🙂": 4, "😊": 5}
        dash_m_cols = st.columns(5)
        for mi, (mc, me) in enumerate(zip(dash_m_cols, mood_emojis)):
            with mc:
                if st.button(me, key=f"dash_mlog_{mi}", use_container_width=True):
                    log_mood_db(user["id"], me, mood_scores[me], mood_note_dash or "")
                    st.session_state.mood = me
                    st.session_state["dash_show_log"] = False
                    st.rerun()

    # Load data
    entries = get_mood_history(user["id"], days=30)
    summary_7 = get_mood_summary(user["id"], days=7)
    summary_30 = get_mood_summary(user["id"], days=30)

    if not entries:
        st.html('<div style="text-align:center;color:#555;padding:60px 0;font-size:0.9rem;">No mood data yet. Log your first mood above!</div>')
        return

    # ── STAT CARDS ──
    mood_emojis_map = {1: "😢", 2: "😟", 3: "😐", 4: "🙂", 5: "😊"}
    avg_score = summary_30["avg"]
    avg_emoji = mood_emojis_map.get(round(avg_score), "😐")
    trend_sym = {"improving": "↑", "declining": "↓", "stable": "→", "neutral": "→"}.get(summary_7["trend"], "→")
    trend_color = {"improving": "#34c759", "declining": "#ff453a", "stable": "#888", "neutral": "#888"}.get(summary_7["trend"], "#888")

    # Calculate streak
    streak = 0
    if entries:
        dates_logged = set()
        for e in entries:
            try:
                d = dt.datetime.strptime(e["logged_at"][:10], "%Y-%m-%d").date()
                dates_logged.add(d)
            except Exception:
                pass
        today = dt.date.today()
        check = today
        while check in dates_logged:
            streak += 1
            check -= dt.timedelta(days=1)

    st.html(f"""<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-value">{streak}</div>
        <div class="stat-label">Day Streak</div>
        <div class="stat-sub">consecutive days logged</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{avg_emoji} {avg_score:.1f}</div>
        <div class="stat-label">30-Day Average</div>
        <div class="stat-sub">out of 5</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color:{trend_color};">{trend_sym} {summary_7["trend"].title()}</div>
        <div class="stat-label">7-Day Trend</div>
        <div class="stat-sub">{summary_7["count"]} entries this week</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{summary_30["count"]}</div>
        <div class="stat-label">Total Entries</div>
        <div class="stat-sub">last 30 days</div>
    </div>
</div>""")

    theme = plotly_dark_theme()

    # ── CHART 1: 30-Day Mood Timeline ──
    st.html('<div style="font-size:0.82rem;font-weight:600;color:#888;margin:20px 0 8px;text-transform:uppercase;letter-spacing:0.05em;">30-Day Timeline</div>')

    import pandas as pd
    df = pd.DataFrame(entries)
    df["logged_at"] = pd.to_datetime(df["logged_at"])
    df = df.sort_values("logged_at")

    fig1 = go.Figure()

    # Individual points colored by score
    for score_val in [1, 2, 3, 4, 5]:
        mask = df["mood_score"] == score_val
        sub = df[mask]
        if not sub.empty:
            fig1.add_trace(go.Scatter(
                x=sub["logged_at"],
                y=sub["mood_score"],
                mode="markers",
                marker=dict(color=MOOD_COLORS[score_val], size=6, opacity=0.7),
                name=f"Score {score_val}",
                showlegend=False,
            ))

    # Rolling 3-day average
    df_daily = df.set_index("logged_at").resample("D")["mood_score"].mean().reset_index()
    df_daily["rolling"] = df_daily["mood_score"].rolling(3, min_periods=1).mean()
    fig1.add_trace(go.Scatter(
        x=df_daily["logged_at"],
        y=df_daily["rolling"],
        mode="lines",
        line=dict(color="#0a84ff", width=2),
        name="3-day avg",
        showlegend=True,
    ))

    fig1.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888', family='Inter'),
        xaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a'),
        yaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a', range=[0.5, 5.5],
                   tickvals=[1, 2, 3, 4, 5], ticktext=["😢", "😟", "😐", "🙂", "😊"]),
        legend=dict(font=dict(color="#666", size=10), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=40, r=20, t=20, b=40),
        height=220,
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ── CHART 2: Weekly Averages ──
    st.html('<div style="font-size:0.82rem;font-weight:600;color:#888;margin:20px 0 8px;text-transform:uppercase;letter-spacing:0.05em;">Weekly Averages</div>')

    df["week"] = df["logged_at"].dt.to_period("W").apply(lambda r: r.start_time)
    weekly = df.groupby("week")["mood_score"].mean().reset_index()
    weekly = weekly.tail(4)
    week_labels = [w.strftime("%-m/%-d") for w in weekly["week"]]
    week_colors = [MOOD_COLORS.get(round(s), "#888") for s in weekly["mood_score"]]

    fig2 = go.Figure(go.Bar(
        x=week_labels,
        y=weekly["mood_score"],
        marker_color=week_colors,
        text=[f"{v:.1f}" for v in weekly["mood_score"]],
        textposition="outside",
        textfont=dict(color="#888", size=10),
    ))
    fig2.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888', family='Inter'),
        xaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a'),
        yaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a', range=[0, 5.8]),
        margin=dict(l=40, r=20, t=20, b=40),
        height=200,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── CHARTS 3 & 4 side by side ──
    col3, col4 = st.columns(2, gap="small")

    with col3:
        st.html('<div style="font-size:0.82rem;font-weight:600;color:#888;margin:8px 0;text-transform:uppercase;letter-spacing:0.05em;">Mood Distribution</div>')
        mood_counts = df["mood"].value_counts().reset_index()
        mood_counts.columns = ["mood", "count"]
        donut_colors = [MOOD_COLORS.get({"😢": 1, "😟": 2, "😐": 3, "🙂": 4, "😊": 5}.get(m, 3), "#888")
                        for m in mood_counts["mood"]]
        fig3 = go.Figure(go.Pie(
            labels=mood_counts["mood"],
            values=mood_counts["count"],
            hole=0.55,
            marker=dict(colors=donut_colors),
            textfont=dict(size=11),
        ))
        fig3.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#888', family='Inter'),
            showlegend=False,
            height=200,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.html('<div style="font-size:0.82rem;font-weight:600;color:#888;margin:8px 0;text-transform:uppercase;letter-spacing:0.05em;">By Day of Week</div>')
        df["dow"] = df["logged_at"].dt.dayofweek
        dow_avg = df.groupby("dow")["mood_score"].mean().reindex(range(7)).fillna(0).reset_index()
        dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        dow_colors = [MOOD_COLORS.get(round(s), "#2a2a2a") if s > 0 else "#2a2a2a"
                      for s in dow_avg["mood_score"]]
        fig4 = go.Figure(go.Bar(
            x=dow_labels,
            y=dow_avg["mood_score"],
            marker_color=dow_colors,
        ))
        fig4.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#888', family='Inter'),
            xaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a'),
            yaxis=dict(gridcolor='#1a1a1a', zerolinecolor='#1a1a1a', range=[0, 5.5]),
            height=200,
            margin=dict(l=20, r=10, t=10, b=30),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ── RECENT ENTRIES ──
    st.html('<div style="font-size:0.82rem;font-weight:600;color:#888;margin:20px 0 8px;text-transform:uppercase;letter-spacing:0.05em;">Recent Entries</div>')
    recent_entries = sorted(entries, key=lambda x: x["logged_at"], reverse=True)[:10]
    for entry in recent_entries:
        try:
            t = dt.datetime.strptime(entry["logged_at"], "%Y-%m-%d %H:%M:%S")
            time_str = t.strftime("%-m/%-d %-I:%M%p").lower()
        except Exception:
            time_str = entry["logged_at"][:16]
        note = html_mod.escape(entry.get("note", "") or "")
        note_html = f'<span class="mood-entry-note">{note}</span>' if note else ""
        st.html(f'<div class="mood-entry-row">'
                f'<span class="mood-entry-time">{time_str}</span>'
                f'<span class="mood-entry-emoji">{entry["mood"]}</span>'
                f'{note_html}'
                f'</div>')

    st.divider()

    # ── Export session ─────────────────────────────────────────────────────────
    if st.session_state.messages:
        session_md = export_session_markdown(
            st.session_state.messages,
            st.session_state.topics,
            st.session_state.mood or "Not recorded",
            st.session_state.care_plan,
            st.session_state.escalation_message,
            st.session_state.governance_scores,
            st.session_state.triage_level,
        )
        filename = f"terpwell-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}.md"
        st.download_button(
            "📥 Export Session",
            data=session_md,
            file_name=filename,
            mime="text/markdown",
            use_container_width=True,
        )

    # ── Clear chat ─────────────────────────────────────────────────────────────
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.crisis_detected = False
        st.session_state.governance_scores = []
        st.session_state.sentiment_scores = []
        st.session_state.topics = []
        st.session_state.quick_prompt_selected = None
        st.session_state.care_plan = None
        st.session_state.triage_level = "none"
        st.session_state.escalation_message = None
        st.rerun()

    # ── Logout ─────────────────────────────────────────────────────────────────
    st.html('<div style="height:20px;"></div>')
    if st.button("Logout", key="dash_logout", use_container_width=False):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.html('<div class="disclaimer">TerpWell is not a substitute for professional help. If you\'re in crisis, call 988 or UMD CAPS: (301) 314-7651</div>')


def render_chat_screen():
    import html as html_mod

    user = st.session_state.user
    mood_display = f" · {st.session_state.mood}" if st.session_state.mood else ""

    # ── HUMAN ESCALATION PANEL ────────────────────────────────────────────────
    if st.session_state.crisis_detected and st.session_state.triage_level in ("mild", "urgent"):
        st.html(
            """<div style="background:rgba(20,184,166,0.06);border:1px solid rgba(20,184,166,0.25);
                           border-radius:14px;padding:1.1rem 1.3rem;margin-bottom:1rem;">
                <div style="font-size:0.95rem;font-weight:600;color:#5eead4;margin-bottom:0.25rem;">
                    🤝 Connect with Real Support
                </div>
                <div style="font-size:0.82rem;color:#71717a;margin-bottom:0.9rem;">
                    A trained human can help in ways an AI cannot.
                    Here's a message you can share with CAPS, an RA, or a trusted person.
                </div>
            </div>"""
        )

        contact_cols = st.columns(3)
        contacts = [
            ("📞", "988 Lifeline", "Call or text 988", "tel:988"),
            ("📞", "UMD CAPS", "(301) 314-7651", "tel:3013147651"),
            ("💬", "Crisis Text", "Text HOME to 741741", None),
        ]
        for col, (icon, name, detail, link) in zip(contact_cols, contacts):
            with col:
                link_html = f"<a href='{link}' style='color:#14b8a6;text-decoration:none;'>{detail}</a>" if link else detail
                st.html(
                    f"""<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                   border-radius:10px;padding:0.6rem 0.8rem;text-align:center;">
                        <div style="font-size:1.1rem;">{icon}</div>
                        <div style="font-size:0.8rem;font-weight:600;color:#e4e4e7;margin:3px 0;">{name}</div>
                        <div style="font-size:0.75rem;color:#71717a;">{link_html}</div>
                    </div>"""
                )

        st.html("<div style='height:0.6rem'></div>")

        if st.session_state.escalation_message:
            st.html(
                "<div style='font-size:0.78rem;color:#71717a;margin-bottom:0.3rem;'>"
                "Edit this to feel like your own words, then copy and send:</div>"
            )
            edited = st.text_area(
                "Your message",
                value=st.session_state.escalation_message,
                height=120,
                label_visibility="collapsed",
                key="escalation_text",
            )
            regen_col, _ = st.columns([1, 3])
            with regen_col:
                if st.button("🔄 Regenerate", key="regen_escalation"):
                    with st.spinner("Rewriting…"):
                        st.session_state.escalation_message = generate_escalation_message(
                            st.session_state.messages,
                            st.session_state.mood or "Not specified",
                        )
                    st.rerun()
        else:
            if st.button("✍️ Draft My Message", use_container_width=True, key="gen_escalation"):
                with st.spinner("Drafting your message…"):
                    st.session_state.escalation_message = generate_escalation_message(
                        st.session_state.messages,
                        st.session_state.mood or "Not specified",
                    )
                st.rerun()

    # ── HEADER ──
    hdr_left, hdr_center, hdr_right = st.columns([0.15, 0.70, 0.15], gap="small")
    with hdr_left:
        if st.button("📊", key="mood_dash_toggle", use_container_width=False):
            st.session_state.screen = "mood_dashboard"
            st.session_state.show_resources = False
            st.rerun()
    with hdr_center:
        st.html(f"""<div style="text-align:center;padding-top:2px;">
            <div style="font-size:1rem;font-weight:600;color:#fff;">🐢 TerpWell{mood_display}</div>
            <div style="font-size:0.72rem;color:#555;margin-top:2px;">wellness companion · governed by AI</div>
        </div>""")
    with hdr_right:
        if st.button("📋", key="res_toggle", use_container_width=False):
            st.session_state.show_resources = not st.session_state.show_resources
            st.rerun()

    st.html('<div style="border-bottom:1px solid #1a1a1a;margin-bottom:12px;"></div>')

    # ── RESOURCES PANEL ──
    if st.session_state.show_resources:
        st.html("""<div class="resources-panel">
    <div class="resources-panel-title">Emergency &amp; Campus Resources</div>

    <div class="resource-item">
        <div class="resource-icon-box crisis">🚨</div>
        <div class="resource-info">
            <div class="resource-name">988 Suicide &amp; Crisis Lifeline</div>
            <div class="resource-phone">Call or text 988 · 24/7 free</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box crisis">💬</div>
        <div class="resource-info">
            <div class="resource-name">Crisis Text Line</div>
            <div class="resource-phone">Text HOME to 741741</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box counsel">🧠</div>
        <div class="resource-info">
            <div class="resource-name">UMD CAPS (Counseling)</div>
            <div class="resource-phone">(301) 314-7651 · press 1 after hours</div>
            <div class="resource-desc">Shoemaker Building, 1st floor · Free for students</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box health">🏥</div>
        <div class="resource-info">
            <div class="resource-name">UMD Health Center</div>
            <div class="resource-phone">(301) 314-8180</div>
            <div class="resource-desc">Campus Drive · Physical &amp; mental health</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box safety">🚔</div>
        <div class="resource-info">
            <div class="resource-name">Campus Police</div>
            <div class="resource-phone">911 or (301) 405-3333</div>
            <div class="resource-desc">Emergency services</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box safety">💜</div>
        <div class="resource-info">
            <div class="resource-name">CARE to Stop Violence</div>
            <div class="resource-phone">(301) 314-2222</div>
            <div class="resource-desc">Sexual assault &amp; relationship violence support</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box counsel">🎓</div>
        <div class="resource-info">
            <div class="resource-name">Dean of Students</div>
            <div class="resource-phone">(301) 314-8783</div>
            <div class="resource-desc">Academic concerns &amp; personal emergencies</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box health">🏠</div>
        <div class="resource-info">
            <div class="resource-name">Resident Life 24/7 Duty Line</div>
            <div class="resource-phone">(301) 314-9237</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box access">♿</div>
        <div class="resource-info">
            <div class="resource-name">Accessibility &amp; Disability Service (ADS)</div>
            <div class="resource-phone">(301) 314-7682 · ads.umd.edu</div>
            <div class="resource-desc">ADHD, learning disabilities, autism support · Free for registered students</div>
        </div>
    </div>

    <div class="resource-item">
        <div class="resource-icon-box access">📚</div>
        <div class="resource-info">
            <div class="resource-name">ADHD/LD Coaching (via ADS)</div>
            <div class="resource-phone">ads.umd.edu/services/coaching</div>
            <div class="resource-desc">Free 1-on-1 coaching for registered students</div>
        </div>
    </div>

</div>""")
        # Logout in resources panel
        if st.button("Logout", key="chat_logout", use_container_width=False):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ── CRISIS BANNER ──
    if st.session_state.crisis_detected:
        st.html("""<div class="crisis-card">
    <div class="crisis-title">If you're in crisis, help is available now</div>
    <div class="crisis-body">
        📞 988 Suicide &amp; Crisis Lifeline (call or text)<br>
        📞 UMD CAPS: (301) 314-7651<br>
        💬 Crisis Text Line: Text HOME to 741741
    </div>
</div>""")

    # ── WELCOME SCREEN ──
    if not st.session_state.messages and not st.session_state.pending_prompt:
        display_name = user["display_name"].split()[0] if user else "Terp"
        st.html(f"""<div class="welcome-container">
    <div class="welcome-icon">🐢</div>
    <div class="welcome-title">Hey, {html_mod.escape(display_name)}.</div>
    <div class="welcome-sub">How's your day going? I'm here to listen.</div>
</div>""")

        st.html('<div style="text-align:center;color:#666;font-size:0.82rem;margin:16px 0 8px;">How are you feeling?</div>')
        moods = ["😢", "😟", "😐", "🙂", "😊"]
        mood_scores = {"😢": 1, "😟": 2, "😐": 3, "🙂": 4, "😊": 5}
        cols = st.columns(5)
        for i, (col, emoji) in enumerate(zip(cols, moods)):
            with col:
                if st.button(emoji, key=f"mood_{i}", use_container_width=True):
                    st.session_state.mood = emoji
                    if user:
                        log_mood_db(user["id"], emoji, mood_scores[emoji], "")
                    st.rerun()

        st.html('<div style="height:24px"></div>')
        suggestions = [
            "Midterms are crushing me right now",
            "I don't really have friends on campus yet",
            "I need a place to decompress near UMD",
            "I can't stop procrastinating and I feel awful",
        ]
        for i, s in enumerate(suggestions):
            if st.button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state.pending_prompt = s
                st.rerun()

    # ── PENDING PROMPT (show thinking while processing) ──
    elif st.session_state.pending_prompt and not st.session_state.messages:
        st.html('<div class="thinking"><div class="thinking-dots"><span></span><span></span><span></span></div><span class="thinking-text">thinking...</span></div>')

    # ── CHAT MESSAGES ──
    elif st.session_state.messages:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                escaped = html_mod.escape(msg["content"]).replace("\n", "<br>")
                st.html(f'<div class="msg-row-user"><div class="msg-bubble-user">{escaped}</div></div>')
            else:
                avatar_col, content_col = st.columns([0.06, 0.94], gap="small")
                with avatar_col:
                    st.html('<div class="msg-avatar">🐢</div>')
                with content_col:
                    st.markdown(msg["content"])
                    audit = msg.get("audit", {})
                    was_corrected = msg.get("was_corrected", False)
                    if was_corrected:
                        st.html('<div class="gov-tag reviewed">🛡️ Reviewed &amp; Corrected</div>')
                    elif audit.get("approved", True):
                        st.html('<div class="gov-tag verified">🛡️ Verified</div>')
                    else:
                        st.html('<div class="gov-tag reviewed">🛡️ Reviewed</div>')

    # ── COPING TOOLS ──
    st.html('<div style="margin-top:1rem;margin-bottom:0.5rem;font-size:0.72rem;color:#52525b;'
            'text-transform:uppercase;letter-spacing:0.08em;">Coping Tools</div>')
    tool_col1, tool_col2, tool_col3 = st.columns(3)
    with tool_col1:
        if st.button("🫁 Breathing", use_container_width=True, key="tool_breathing"):
            st.session_state.breathing_active = not st.session_state.breathing_active
            st.session_state.breathing_phase = "in"
            st.session_state.breathing_count = 0
            st.rerun()
    with tool_col2:
        if st.button("📝 Journal", use_container_width=True, key="tool_journal"):
            st.session_state.journal_prompt = random.choice(JOURNAL_PROMPTS)
            st.rerun()
    with tool_col3:
        if st.button("🧘 Grounding", use_container_width=True, key="tool_grounding"):
            st.session_state.show_grounding = not st.session_state.show_grounding
            st.session_state.grounding_checks = [False] * 5
            st.rerun()

    # ── Breathing Exercise ────────────────────────────────────────────────────
    if st.session_state.breathing_active:
        phase_labels = {
            "in": ("Breathe In...", "#14b8a6", "breatheIn 4s ease-in-out forwards"),
            "hold": ("Hold...", "#8b5cf6", "breatheHold 4s ease-in-out forwards"),
            "out": ("Breathe Out...", "#a78bfa", "breatheOut 4s ease-in-out forwards"),
        }
        phase = st.session_state.breathing_phase
        label, color, anim = phase_labels[phase]
        st.html(
            f"""<div class="glass-card" style="text-align:center;padding:1.5rem;">
                <div style="font-size:0.85rem;color:#71717a;margin-bottom:1rem;">
                    4-4-4 Box Breathing · Cycle {st.session_state.breathing_count + 1}
                </div>
                <div style="
                    width:110px;height:110px;
                    background:radial-gradient(circle,{color}33 0%,{color}08 70%);
                    border:2px solid {color}66;border-radius:50%;
                    margin:0 auto 1rem;animation:{anim};
                    display:flex;align-items:center;justify-content:center;font-size:2.2rem;
                ">🫁</div>
                <div style="font-size:1.3rem;font-weight:600;color:{color};">{label}</div>
                <div style="font-size:0.78rem;color:#71717a;margin-top:0.3rem;">4 seconds</div>
            </div>"""
        )
        bcol1, bcol2, bcol3 = st.columns([1, 2, 1])
        with bcol2:
            phase_order = ["in", "hold", "out"]
            if st.button("Next Phase ▶", use_container_width=True, key="breath_next"):
                idx = phase_order.index(st.session_state.breathing_phase)
                next_idx = (idx + 1) % len(phase_order)
                st.session_state.breathing_phase = phase_order[next_idx]
                if next_idx == 0:
                    st.session_state.breathing_count += 1
                st.rerun()
            if st.button("Stop Breathing Exercise", use_container_width=True, key="breath_stop"):
                st.session_state.breathing_active = False
                st.rerun()

    # ── Journal Prompt ────────────────────────────────────────────────────────
    if st.session_state.journal_prompt and not st.session_state.breathing_active:
        st.html(
            f"""<div class="glass-card" style="border-left:3px solid #8b5cf6;padding:1rem 1.2rem;">
                <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;
                            color:#71717a;margin-bottom:0.4rem;">📝 Journal Prompt</div>
                <div style="font-size:0.95rem;color:#e4e4e7;line-height:1.6;">{st.session_state.journal_prompt}</div>
                <div style="font-size:0.75rem;color:#52525b;margin-top:0.5rem;">
                    Take a moment to reflect. You don't need to share,just write for yourself.
                </div>
            </div>"""
        )
        jcol1, jcol2 = st.columns([1, 1])
        with jcol1:
            if st.button("New Prompt", use_container_width=True, key="journal_new"):
                st.session_state.journal_prompt = random.choice(JOURNAL_PROMPTS)
                st.rerun()
        with jcol2:
            if st.button("Close", key="journal_close", use_container_width=True):
                st.session_state.journal_prompt = None
                st.rerun()

    # ── Grounding Exercise ────────────────────────────────────────────────────
    if st.session_state.show_grounding and not st.session_state.breathing_active:
        st.html(
            """<div class="glass-card" style="border-left:3px solid #14b8a6;">
                <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;
                            color:#71717a;margin-bottom:0.5rem;">🧘 5-4-3-2-1 Grounding Technique</div>
                <div style="font-size:0.82rem;color:#71717a;margin-bottom:0.8rem;">
                    Check each box as you complete each step. This brings you back to the present moment.
                </div>
            </div>"""
        )
        all_done = True
        for i, (title, instruction) in enumerate(GROUNDING_STEPS):
            checked = st.checkbox(
                f"**{title}**  \n{instruction}",
                value=st.session_state.grounding_checks[i],
                key=f"ground_{i}",
            )
            st.session_state.grounding_checks[i] = checked
            if not checked:
                all_done = False
        if all_done:
            st.html(
                """<div style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);
                              border-radius:10px;padding:0.7rem;text-align:center;
                              font-size:0.88rem;color:#4ade80;margin-top:0.5rem;">
                    ✅ Great job! You've completed the grounding exercise. How do you feel?
                </div>"""
            )
        if st.button("Close Grounding Exercise", key="grounding_close"):
            st.session_state.show_grounding = False
            st.rerun()

    # ── STATUS PLACEHOLDER ──
    status_ph = st.empty()

    # ── INPUT HANDLING ──
    if st.session_state.pending_prompt:
        user_input = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
    else:
        user_input = st.chat_input("What's on your mind?")

    st.html('<div class="disclaimer">TerpWell is not a substitute for professional help. If you\'re in crisis, call 988 or UMD CAPS: (301) 314-7651</div>')

    # ── PROCESS MESSAGE ──
    if user_input:
        raw_text = user_input.strip()
        if not raw_text:
            st.stop()

        # Fast regex crisis check first
        if detect_crisis(raw_text):
            st.session_state.crisis_detected = True

        # Extract topics
        st.session_state.topics.extend(extract_topics(raw_text))

        st.session_state.messages.append({
            "role": "user",
            "content": raw_text,
            "timestamp": time.time(),
        })

        # Save user message to DB
        if user and st.session_state.chat_session_id:
            save_chat_message(st.session_state.chat_session_id, user["id"], "user", raw_text)

        # Build API history (exclude the just-added user message)
        api_history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
            if m["role"] in ("user", "assistant")
        ]

        # Show user bubble inline so it appears before streaming
        escaped = html_mod.escape(raw_text).replace("\n", "<br>")
        st.html(f'<div class="msg-row-user"><div class="msg-bubble-user">{escaped}</div></div>')

        # Streaming assistant bubble
        avatar_col, content_col = st.columns([0.06, 0.94], gap="small")
        with avatar_col:
            st.html('<div class="msg-avatar">🐢</div>')
        with content_col:
            stream_placeholder = st.empty()

        try:
            # Stream companion response word-by-word
            draft = stream_companion(raw_text, st.session_state.mood or "Not specified", api_history, stream_placeholder)

            # Claude-powered crisis detection (catches nuanced signals regex misses)
            with st.spinner("🛡️ Auditing response…"):
                crisis_result = detect_crisis_claude(raw_text)
                level = crisis_result.get("crisis_level", "none")
                st.session_state.triage_level = level
                if level in ("mild", "urgent"):
                    st.session_state.crisis_detected = True
                    if not st.session_state.escalation_message:
                        st.session_state.escalation_message = generate_escalation_message(
                            st.session_state.messages,
                            st.session_state.mood or "Not specified",
                        )

                # Run governance AFTER streaming completes
                audit, was_corrected = run_governance(raw_text, draft)

            final_response = audit.pop("_final", draft)

            # Record governance score and sentiment
            st.session_state.governance_scores.append(audit.get("score", 100))
            sentiment = audit.get("sentiment_score", 3)
            if isinstance(sentiment, int) and 1 <= sentiment <= 5:
                st.session_state.sentiment_scores.append(sentiment)

            # Save assistant message to DB
            if user and st.session_state.chat_session_id:
                save_chat_message(
                    st.session_state.chat_session_id, user["id"], "assistant",
                    final_response, json.dumps(audit)
                )

            st.session_state.messages.append({
                "role": "assistant",
                "content": final_response,
                "timestamp": time.time(),
                "audit": audit,
                "was_corrected": was_corrected,
            })
            st.rerun()

        except anthropic.AuthenticationError:
            status_ph.empty()
            st.error("Authentication failed. Please set ANTHROPIC_API_KEY or configure AWS credentials.")
        except anthropic.RateLimitError:
            status_ph.empty()
            st.error("Rate limit reached. Please wait a moment and try again.")
        except anthropic.APIConnectionError:
            status_ph.empty()
            st.error("Connection error. Please check your internet connection.")
        except Exception as e:
            status_ph.empty()
            st.error(f"Something went wrong: {str(e)}")



# ── MAIN ROUTING ──────────────────────────────────────────────────────────────

if not st.session_state.logged_in:
    render_login_screen()
elif st.session_state.screen == "mood_dashboard":
    render_mood_dashboard()
else:
    render_chat_screen()
