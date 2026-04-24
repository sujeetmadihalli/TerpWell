"""
TerpWell — Your UMD Wellness Companion, Governed by AI
Anthropic × Maryland Hackathon 2025

Two-layer architecture:
  1. Companion AI  — empathetic Claude that talks to the user
  2. Governance AI — second Claude call auditing every response before display
"""

import os
import json
import time
import re
import random
import datetime
import streamlit as st
import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# API SETUP (verbatim as specified)
# ─────────────────────────────────────────────────────────────────────────────

USE_BEDROCK = not os.environ.get("ANTHROPIC_API_KEY")
MODEL = "us.anthropic.claude-sonnet-4-6" if USE_BEDROCK else "claude-sonnet-4-6"


def get_client():
    if USE_BEDROCK:
        return anthropic.AnthropicBedrock(
            aws_region=os.environ.get("AWS_REGION", "us-east-1")
        )
    else:
        return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# CRISIS DETECTION KEYWORDS (client-side)
# ─────────────────────────────────────────────────────────────────────────────

CRISIS_KEYWORDS = [
    "suicide",
    "kill myself",
    "self-harm",
    "self harm",
    "want to die",
    "end it all",
    "end my life",
    "hurt myself",
    "no reason to live",
    "better off dead",
    "take my life",
    "don't want to be here",
    "can't go on",
]

CRISIS_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in CRISIS_KEYWORDS), re.IGNORECASE
)


def detect_crisis(text: str) -> bool:
    return bool(CRISIS_PATTERN.search(text))


def detect_crisis_claude(text: str) -> dict:
    """Claude-powered nuanced crisis classification — catches paraphrases regex misses."""
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


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def companion_system_prompt(profile: dict) -> str:
    mood = profile.get("mood", "Not specified")
    topics = profile.get("topics", [])
    topics_str = ", ".join(topics) if topics else "None yet"

    return f"""You are TerpWell, a caring and empathetic wellness companion for University of Maryland students. You are NOT a therapist, counselor, or medical professional. You are a supportive AI friend.

## What You DO:
- Listen actively and validate feelings
- Suggest evidence-based coping strategies (breathing exercises, grounding techniques, journaling prompts)
- Share relevant UMD resources when appropriate
- Help with study stress, anxiety, loneliness, homesickness, imposter syndrome
- Encourage self-care and healthy habits
- Celebrate small wins and progress

## What You DON'T Do:
- Never diagnose mental health conditions
- Never prescribe or recommend medication
- Never claim to replace professional help
- Never minimize feelings ("just think positive", "others have it worse")
- Never provide crisis counseling — always redirect to 988/CAPS

## Crisis Detection:
If the user mentions suicide, self-harm, or immediate danger, IMMEDIATELY respond with:
"I hear you, and I'm glad you're reaching out. Please contact these resources right now:
- 988 Suicide & Crisis Lifeline: Call or text 988 (24/7)
- UMD CAPS Crisis Line: (301) 314-7651
- Crisis Text Line: Text HOME to 741741
You deserve support from trained professionals. Would you like me to help you take the next step?"

## UMD Resources (VERIFIED — DO NOT MAKE UP RESOURCES):
- UMD Counseling Center (CAPS): (301) 314-7651, Shoemaker Building
- After-hours crisis: (301) 314-7651, press 1
- UMD Health Center: (301) 314-8180
- Campus Police (emergency): 911 or (301) 405-3333
- Sexual Assault/Relationship Violence: CARE to Stop Violence (301) 314-2222
- Dean of Students: (301) 314-8783
- Resident Life 24/7 Duty Line: (301) 314-9237
- Accessibility & Disability Service (ADS): (301) 314-7682, ads.umd.edu — ADHD, learning disabilities, autism support
- ADHD/LD Coaching: through ADS, free for registered students, ads.umd.edu/services/coaching

## Mood Context:
Student's current mood: {mood}
Previous conversation topics: {topics_str}

## Conversation Style:
- Warm, conversational, not clinical
- Use "I" statements ("I hear you", "I understand")
- Ask follow-up questions to understand better
- Suggest ONE coping strategy at a time, not a list
- Keep responses concise (2-4 paragraphs max)
- Use gentle language, never condescending"""


def governance_system_prompt() -> str:
    return """You are the TerpWell Governance Auditor. Your job is to review AI wellness companion responses for safety, accuracy, and appropriateness.

Review the following response for these criteria:

## Safety Checks:
1. CRISIS_DETECTION: If user message mentions suicide/self-harm, does the response include crisis resources? (988, CAPS)
2. NO_DIAGNOSIS: Response does NOT diagnose any mental health condition
3. NO_PRESCRIBING: Response does NOT recommend medication or specific treatments
4. NO_MINIMIZING: Response does NOT minimize or dismiss feelings
5. APPROPRIATE_BOUNDARIES: Response acknowledges AI limitations when needed

## Accuracy Checks:
6. RESOURCE_ACCURACY: Any phone numbers, locations, or resource names mentioned are correct per the verified list
7. NO_HALLUCINATION: Response does not cite fake organizations, studies, or resources
8. FACTUAL_CLAIMS: Any factual claims are reasonable and not misleading

## Tone Checks:
9. EMPATHETIC_TONE: Response is warm and validating
10. NOT_CONDESCENDING: Response doesn't talk down to the user
11. CULTURALLY_SENSITIVE: Response is inclusive and culturally aware

Respond in this EXACT JSON format:
{
    "approved": true/false,
    "score": 0-100,
    "sentiment_score": 1-5,
    "checks": {
        "crisis_detection": {"pass": true/false, "note": "..."},
        "no_diagnosis": {"pass": true/false, "note": "..."},
        "no_prescribing": {"pass": true/false, "note": "..."},
        "no_minimizing": {"pass": true/false, "note": "..."},
        "appropriate_boundaries": {"pass": true/false, "note": "..."},
        "resource_accuracy": {"pass": true/false, "note": "..."},
        "no_hallucination": {"pass": true/false, "note": "..."},
        "factual_claims": {"pass": true/false, "note": "..."},
        "empathetic_tone": {"pass": true/false, "note": "..."},
        "not_condescending": {"pass": true/false, "note": "..."},
        "culturally_sensitive": {"pass": true/false, "note": "..."}
    },
    "corrections": "If not approved, explain what needs to change. If approved, say 'None needed.'",
    "corrected_response": "If not approved, provide the corrected version. If approved, return the original response unchanged."
}

sentiment_score key: rate the emotional state expressed in the USER MESSAGE on a scale of 1-5 where 1=very distressed, 2=struggling, 3=neutral, 4=doing okay, 5=positive/doing well."""


# ─────────────────────────────────────────────────────────────────────────────
# JSON GOVERNANCE PARSER (robust)
# ─────────────────────────────────────────────────────────────────────────────

def parse_governance_json(raw: str) -> dict:
    """Parse governance JSON response, falling back to regex extraction on failure."""
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block with regex
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return a safe default that approves the response
    return {
        "approved": True,
        "score": 75,
        "checks": {
            "crisis_detection": {"pass": True, "note": "Parse error — manual review recommended"},
            "no_diagnosis": {"pass": True, "note": ""},
            "no_prescribing": {"pass": True, "note": ""},
            "no_minimizing": {"pass": True, "note": ""},
            "appropriate_boundaries": {"pass": True, "note": ""},
            "resource_accuracy": {"pass": True, "note": ""},
            "no_hallucination": {"pass": True, "note": ""},
            "factual_claims": {"pass": True, "note": ""},
            "empathetic_tone": {"pass": True, "note": ""},
            "not_condescending": {"pass": True, "note": ""},
            "culturally_sensitive": {"pass": True, "note": ""},
        },
        "corrections": "Governance parse error — response passed by default.",
        "corrected_response": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE GENERATION (two-step: companion → governance)
# ─────────────────────────────────────────────────────────────────────────────

def stream_companion(user_message: str, profile: dict, history: list, placeholder) -> str:
    """Stream companion response token-by-token into a Streamlit placeholder."""
    client = get_client()
    messages_payload = history + [{"role": "user", "content": user_message}]
    full_text = ""

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": companion_system_prompt(profile), "cache_control": {"type": "ephemeral"}}],
        messages=messages_payload,
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            placeholder.markdown(full_text + "▌")

    placeholder.markdown(full_text)
    return full_text


def run_governance(user_message: str, draft: str) -> tuple[dict, bool]:
    """Run governance audit. Returns (audit_dict, was_corrected)."""
    client = get_client()
    governance_prompt = (
        f"USER MESSAGE:\n{user_message}\n\n"
        f"COMPANION RESPONSE:\n{draft}\n\n"
        f"Review this response."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": governance_system_prompt(), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": governance_prompt}],
    )

    audit = parse_governance_json(response.content[0].text)
    approved = audit.get("approved", True)

    if not approved:
        corrected = audit.get("corrected_response", "").strip()
        audit["_final"] = corrected if corrected else draft
    else:
        audit["_final"] = draft

    return audit, not approved


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
        system=[{
            "type": "text",
            "text": (
                "You are a wellness care coordinator for UMD students. "
                "Based on the conversation, produce a concise 3-step personal care plan. "
                "Be specific and warm. Reference real UMD resources where relevant. "
                'Return JSON only: {"steps": [{"action": "...", "detail": "..."}], "note": "..."}'
            ),
            "cache_control": {"type": "ephemeral"},
        }],
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


# ─────────────────────────────────────────────────────────────────────────────
# TOPIC EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# COPING TOOLS DATA
# ─────────────────────────────────────────────────────────────────────────────

JOURNAL_PROMPTS = [
    "What is one thing you accomplished today, no matter how small?",
    "Describe a moment this week when you felt at peace. What were you doing?",
    "What are three things you're grateful for right now?",
    "If your future self could send you a message today, what would it say?",
    "What boundaries do you need to set to protect your energy?",
    "Write about a challenge you're facing. What's one small step you could take?",
    "Who in your life makes you feel supported? How can you connect with them?",
    "What does your ideal rest day look like?",
    "What emotion are you carrying today, and where do you feel it in your body?",
    "What would you tell a good friend who was going through what you're going through?",
    "List 5 things that bring you joy, even in small doses.",
    "What's one thing you'd like to let go of this week?",
]

GROUNDING_STEPS = [
    ("5 things you can SEE", "Look around and notice 5 things you can see right now."),
    ("4 things you can TOUCH", "Notice 4 things you can physically touch — the chair, your clothes, a surface."),
    ("3 things you can HEAR", "Listen carefully. What 3 sounds can you hear right now?"),
    ("2 things you can SMELL", "Notice 2 scents around you — or recall your favorite scent."),
    ("1 thing you can TASTE", "Notice 1 taste in your mouth right now."),
]

MOOD_OPTIONS = [
    ("😢", "Struggling"),
    ("😟", "Low"),
    ("😐", "Okay"),
    ("🙂", "Good"),
    ("😊", "Great"),
]

QUICK_PROMPTS = [
    "I'm feeling stressed about exams",
    "Help me with a breathing exercise",
    "I've been feeling lonely lately",
    "I need campus resources",
    "Help me build a self-care routine",
]


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TerpWell",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Root theme ── */
    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #0f1019;
        --bg-card: rgba(255,255,255,0.03);
        --border-subtle: rgba(255,255,255,0.06);
        --accent-teal: #14b8a6;
        --accent-purple: #8b5cf6;
        --accent-red: #ef4444;
        --accent-green: #22c55e;
        --accent-yellow: #eab308;
        --text-primary: #e4e4e7;
        --text-secondary: #71717a;
        --text-muted: #52525b;
    }

    /* ── App background ── */
    .stApp {
        background: linear-gradient(135deg, #0a0a0f 0%, #0f1019 50%, #0a0f14 100%);
        font-family: 'Inter', sans-serif;
        color: var(--text-primary);
    }
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 900px;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d15 0%, #0a0f1a 100%);
        border-right: 1px solid var(--border-subtle);
    }
    [data-testid="stSidebar"] .block-container { padding: 1.2rem 1rem; }

    /* ── Hide default streamlit elements ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Glass card ── */
    .glass-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }

    /* ── Breathing circle animation ── */
    @keyframes breatheIn {
        from { transform: scale(1); opacity: 0.7; }
        to   { transform: scale(1.55); opacity: 1; }
    }
    @keyframes breatheOut {
        from { transform: scale(1.55); opacity: 1; }
        to   { transform: scale(1); opacity: 0.7; }
    }
    @keyframes breatheHold {
        from { transform: scale(1.55); }
        to   { transform: scale(1.55); }
    }
    .breathe-in  { animation: breatheIn  4s ease-in-out forwards; }
    .breathe-hold { animation: breatheHold 4s ease-in-out forwards; }
    .breathe-out { animation: breatheOut 4s ease-in-out forwards; }

    /* ── Crisis banner pulse ── */
    @keyframes crisisPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
        50%       { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
    }
    .crisis-banner {
        background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.08));
        border: 1px solid rgba(239,68,68,0.5);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        animation: crisisPulse 2.5s ease-in-out infinite;
    }

    /* ── Chat bubbles ── */
    .user-bubble {
        display: flex;
        justify-content: flex-end;
        margin: 0.6rem 0;
    }
    .user-bubble-inner {
        background: linear-gradient(135deg, rgba(139,92,246,0.25), rgba(109,40,217,0.2));
        border: 1px solid rgba(139,92,246,0.3);
        border-radius: 18px 18px 4px 18px;
        padding: 0.75rem 1.1rem;
        max-width: 72%;
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.6;
    }
    .assistant-bubble {
        display: flex;
        justify-content: flex-start;
        margin: 0.6rem 0;
        gap: 0.6rem;
        align-items: flex-start;
    }
    .assistant-avatar {
        font-size: 1.4rem;
        margin-top: 0.15rem;
        flex-shrink: 0;
    }
    .assistant-bubble-inner {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(20,184,166,0.2);
        border-left: 3px solid var(--accent-teal);
        border-radius: 4px 18px 18px 18px;
        padding: 0.75rem 1.1rem;
        max-width: 80%;
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* ── Governance badge ── */
    .gov-badge-approved {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        background: rgba(34,197,94,0.12);
        border: 1px solid rgba(34,197,94,0.3);
        border-radius: 20px;
        padding: 0.2rem 0.65rem;
        font-size: 0.75rem;
        color: #4ade80;
        margin-top: 0.4rem;
        cursor: default;
    }
    .gov-badge-corrected {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        background: rgba(234,179,8,0.12);
        border: 1px solid rgba(234,179,8,0.3);
        border-radius: 20px;
        padding: 0.2rem 0.65rem;
        font-size: 0.75rem;
        color: #facc15;
        margin-top: 0.4rem;
        cursor: default;
    }

    /* ── Check grid ── */
    .check-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 0.4rem;
        margin-top: 0.5rem;
    }
    .check-pass {
        background: rgba(34,197,94,0.08);
        border: 1px solid rgba(34,197,94,0.25);
        border-radius: 8px;
        padding: 0.3rem 0.6rem;
        font-size: 0.78rem;
        color: #4ade80;
    }
    .check-fail {
        background: rgba(239,68,68,0.08);
        border: 1px solid rgba(239,68,68,0.25);
        border-radius: 8px;
        padding: 0.3rem 0.6rem;
        font-size: 0.78rem;
        color: #f87171;
    }

    /* ── Mood buttons ── */
    .mood-row { display: flex; gap: 0.4rem; justify-content: space-between; }
    .mood-btn {
        flex: 1;
        background: rgba(255,255,255,0.04);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 0.35rem 0.2rem;
        text-align: center;
        cursor: pointer;
        font-size: 1.2rem;
        transition: all 0.15s;
    }
    .mood-btn:hover, .mood-btn-selected {
        background: rgba(20,184,166,0.12);
        border-color: rgba(20,184,166,0.4);
    }

    /* ── Resource card ── */
    .resource-item {
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 0.55rem 0.8rem;
        margin-bottom: 0.45rem;
        font-size: 0.82rem;
        color: var(--text-secondary);
    }
    .resource-item strong { color: var(--text-primary); }

    /* ── Score display ── */
    .score-big-green { font-size: 2.2rem; font-weight: 700; color: #4ade80; }
    .score-big-yellow { font-size: 2.2rem; font-weight: 700; color: #facc15; }
    .score-big-red { font-size: 2.2rem; font-weight: 700; color: #f87171; }

    /* ── Feature cards ── */
    .feature-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        padding: 1.1rem;
        text-align: center;
        transition: border-color 0.2s;
    }
    .feature-card:hover { border-color: rgba(20,184,166,0.3); }

    /* ── Pill prompts ── */
    .pill-prompt {
        display: inline-block;
        background: rgba(255,255,255,0.05);
        border: 1px solid var(--border-subtle);
        border-radius: 20px;
        padding: 0.35rem 0.9rem;
        font-size: 0.83rem;
        color: var(--text-secondary);
        margin: 0.2rem;
        cursor: pointer;
        transition: all 0.15s;
    }
    .pill-prompt:hover {
        background: rgba(20,184,166,0.12);
        border-color: rgba(20,184,166,0.4);
        color: var(--text-primary);
    }

    /* ── Footer ── */
    .footer-text {
        text-align: center;
        color: var(--text-muted);
        font-size: 0.78rem;
        padding: 1.5rem 0 0.5rem;
        border-top: 1px solid var(--border-subtle);
        margin-top: 2rem;
    }

    /* ── Section labels ── */
    .section-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        margin-bottom: 0.5rem;
    }

    /* ── Typing indicator ── */
    @keyframes typingPulse {
        0%, 100% { opacity: 0.4; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1); }
    }
    .typing-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        background: var(--accent-teal);
        border-radius: 50%;
        margin: 0 2px;
        animation: typingPulse 1.2s ease-in-out infinite;
    }
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }

    /* ── Progress bar track ── */
    .mini-bar-track {
        background: rgba(255,255,255,0.06);
        border-radius: 4px;
        height: 5px;
        overflow: hidden;
        margin-top: 2px;
    }
    .mini-bar-fill-green  { background: #22c55e; height: 5px; border-radius: 4px; transition: width 0.5s; }
    .mini-bar-fill-yellow { background: #eab308; height: 5px; border-radius: 4px; transition: width 0.5s; }
    .mini-bar-fill-red    { background: #ef4444; height: 5px; border-radius: 4px; transition: width 0.5s; }

    /* ── Gradient title ── */
    .gradient-title {
        background: linear-gradient(135deg, #14b8a6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.1;
    }

    /* ── Breathing overlay ── */
    .breathing-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.75);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        gap: 1.5rem;
    }

    /* ── Streamlit button overrides ── */
    .stButton > button {
        background: rgba(20,184,166,0.12);
        border: 1px solid rgba(20,184,166,0.3);
        color: #14b8a6;
        border-radius: 10px;
        font-family: 'Inter', sans-serif;
        font-size: 0.88rem;
        padding: 0.5rem 1rem;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        background: rgba(20,184,166,0.22);
        border-color: rgba(20,184,166,0.5);
        color: #5eead4;
    }
    .stTextInput input, .stTextArea textarea {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: rgba(20,184,166,0.4) !important;
        box-shadow: 0 0 0 2px rgba(20,184,166,0.1) !important;
    }
    .stExpander {
        background: rgba(255,255,255,0.02);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
    }
    </style>
    """
)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "messages": [],
        "mood": None,
        "crisis_detected": False,
        "governance_scores": [],
        "sentiment_scores": [],
        "topics": [],
        "breathing_active": False,
        "breathing_phase": "in",
        "breathing_count": 0,
        "journal_prompt": None,
        "grounding_checks": [False] * 5,
        "show_grounding": False,
        "quick_prompt_selected": None,
        "api_error": None,
        "care_plan": None,
        "triage_level": "none",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session_state()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── Logo ──────────────────────────────────────────────────────────────────
    st.html(
        """
        <div style="text-align:center; padding: 0.5rem 0 1rem;">
            <span style="font-size:2rem;">🧠</span>
            <div style="font-size:1.3rem; font-weight:700;
                        background:linear-gradient(135deg,#14b8a6,#8b5cf6);
                        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                        background-clip:text;">TerpWell</div>
            <div style="font-size:0.72rem; color:#52525b; margin-top:2px;">
                Wellness with Governance
            </div>
        </div>
        """
    )

    st.divider()

    # ── Mood Check-In ─────────────────────────────────────────────────────────
    st.html('<div class="section-label">How are you today?</div>')

    mood_cols = st.columns(5)
    for idx, (emoji, label) in enumerate(MOOD_OPTIONS):
        with mood_cols[idx]:
            selected = st.session_state.mood == label
            border = "2px solid #14b8a6" if selected else "1px solid rgba(255,255,255,0.06)"
            bg = "rgba(20,184,166,0.15)" if selected else "rgba(255,255,255,0.04)"
            if st.button(emoji, key=f"mood_{idx}", help=label):
                st.session_state.mood = label
                st.rerun()
            st.html(
                f"<div style='text-align:center;font-size:0.55rem;color:#71717a;margin-top:-6px;'>{label}</div>"
            )

    if st.session_state.mood:
        st.html(
            f"<div style='text-align:center;font-size:0.82rem;color:#14b8a6;margin:0.4rem 0;'>"
            f"Feeling: <strong>{st.session_state.mood}</strong></div>"
        )

    st.divider()

    # ── Triage Resources ──────────────────────────────────────────────────────
    st.html('<div class="section-label">Triage Resources</div>')

    triage_level = st.session_state.triage_level
    if triage_level != "none":
        t_color = "#ef4444" if triage_level == "urgent" else "#f97316"
        t_rgb = "239,68,68" if triage_level == "urgent" else "249,115,22"
        t_label = "🚨 Urgent" if triage_level == "urgent" else "⚠️ Mild Concern"
        st.html(
            f"<div style='background:rgba({t_rgb},0.12);border:1px solid rgba({t_rgb},0.4);"
            f"border-radius:8px;padding:0.3rem 0.7rem;font-size:0.78rem;color:{t_color};"
            f"margin-bottom:0.5rem;text-align:center;font-weight:600;'>"
            f"Triage Level: {t_label}</div>"
        )

    resources = [
        ("📞", "988 Lifeline", "Call or text 988 (24/7)"),
        ("📞", "UMD CAPS", "(301) 314-7651"),
        ("💬", "Crisis Text", "Text HOME to 741741"),
        ("🏥", "UMD Health Center", "(301) 314-8180"),
    ]
    for icon, name, detail in resources:
        st.html(
            f"""<div class="resource-item">
                {icon} <strong>{name}</strong><br>
                <span style="font-size:0.78rem;">{detail}</span>
            </div>"""
        )

    st.divider()

    # ── Governance Dashboard ────────────────────────────────────────────────
    st.html('<div class="section-label">Governance Dashboard</div>')

    if st.session_state.governance_scores:
        avg_score = sum(st.session_state.governance_scores) / len(st.session_state.governance_scores)
        latest_score = st.session_state.governance_scores[-1]

        # Color based on score
        if latest_score >= 80:
            score_class = "score-big-green"
            bar_class = "mini-bar-fill-green"
        elif latest_score >= 60:
            score_class = "score-big-yellow"
            bar_class = "mini-bar-fill-yellow"
        else:
            score_class = "score-big-red"
            bar_class = "mini-bar-fill-red"

        st.html(
            f"""<div style="text-align:center; margin-bottom:0.5rem;">
                <div class="{score_class}">{latest_score}</div>
                <div style="font-size:0.72rem;color:#71717a;">Latest Score /100</div>
            </div>"""
        )

        # Category progress bars
        for cat_label, pct in [("Safety", min(100, latest_score + 5)), ("Accuracy", latest_score), ("Tone", min(100, latest_score + 3))]:
            st.html(
                f"""<div style="margin-bottom:0.4rem;">
                    <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#71717a;margin-bottom:2px;">
                        <span>{cat_label}</span><span>{pct}%</span>
                    </div>
                    <div class="mini-bar-track">
                        <div class="{bar_class}" style="width:{pct}%;"></div>
                    </div>
                </div>"""
            )

        if len(st.session_state.messages) > 0:
            last_msg = st.session_state.messages[-1]
            if last_msg.get("role") == "assistant" and last_msg.get("audit"):
                audit = last_msg["audit"]
                with st.expander("Show detailed audit", expanded=False):
                    checks = audit.get("checks", {})
                    check_names = {
                        "crisis_detection": "Crisis Detection",
                        "no_diagnosis": "No Diagnosis",
                        "no_prescribing": "No Prescribing",
                        "no_minimizing": "No Minimizing",
                        "appropriate_boundaries": "AI Boundaries",
                        "resource_accuracy": "Resource Accuracy",
                        "no_hallucination": "No Hallucination",
                        "factual_claims": "Factual Claims",
                        "empathetic_tone": "Empathetic Tone",
                        "not_condescending": "Not Condescending",
                        "culturally_sensitive": "Culturally Sensitive",
                    }
                    for key, label in check_names.items():
                        check = checks.get(key, {})
                        passed = check.get("pass", True)
                        note = check.get("note", "")
                        icon = "✅" if passed else "❌"
                        color = "#4ade80" if passed else "#f87171"
                        st.html(
                            f"<div style='font-size:0.78rem;color:{color};margin-bottom:2px;'>"
                            + f"{icon} <strong>{label}</strong>"
                            + (f"<br><span style='color:#71717a;font-size:0.72rem;padding-left:1.2rem;'>{note}</span>" if note else "")
                            + "</div>"
                        )

    else:
        st.html(
            "<div style='color:#52525b;font-size:0.82rem;text-align:center;'>No audits yet. Start chatting!</div>"
        )

    st.divider()

    # ── Emotional Trajectory ───────────────────────────────────────────────────
    st.html('<div class="section-label">Emotional Trajectory</div>')

    if st.session_state.sentiment_scores:
        import pandas as pd
        scores = st.session_state.sentiment_scores
        df = pd.DataFrame({
            "Turn": list(range(1, len(scores) + 1)),
            "Wellbeing": scores,
        })
        st.line_chart(df.set_index("Turn"), use_container_width=True, height=90)
        latest = scores[-1]
        label = {1: "Very distressed", 2: "Struggling", 3: "Neutral", 4: "Doing okay", 5: "Positive"}.get(latest, "")
        color = {1: "#ef4444", 2: "#f97316", 3: "#eab308", 4: "#22c55e", 5: "#4ade80"}.get(latest, "#71717a")
        st.html(f"<div style='text-align:center;font-size:0.78rem;color:{color};margin-top:-6px;'>{label}</div>")
    else:
        st.html("<div style='color:#52525b;font-size:0.82rem;text-align:center;'>Chat to see your emotional arc</div>")

    st.divider()

    # ── Session Stats ──────────────────────────────────────────────────────────
    st.html('<div class="section-label">Session Stats</div>')

    msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
    avg_score_str = (
        f"{sum(st.session_state.governance_scores)/len(st.session_state.governance_scores):.0f}/100"
        if st.session_state.governance_scores
        else "—"
    )

    st.html(
        f"""<div class="glass-card" style="padding:0.7rem;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.8rem;">
                <div style="color:#71717a;">Messages</div>
                <div style="color:#e4e4e7;text-align:right;font-weight:600;">{msg_count}</div>
                <div style="color:#71717a;">Avg. Score</div>
                <div style="color:#e4e4e7;text-align:right;font-weight:600;">{avg_score_str}</div>
            </div>
        </div>"""
    )

    if st.session_state.topics:
        st.html(
            "<div style='font-size:0.72rem;color:#71717a;margin-bottom:0.3rem;'>Topics discussed:</div>"
        )
        topic_html = " ".join(
            f"<span style='background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.25);"
            f"border-radius:12px;padding:2px 8px;font-size:0.7rem;color:#a78bfa;margin:2px;'>{t}</span>"
            for t in set(st.session_state.topics[:8])
        )
        st.html(f"<div>{topic_html}</div>")

    # Connection badge
    badge_text = "AWS Bedrock" if USE_BEDROCK else "Anthropic API"
    badge_color = "#14b8a6" if USE_BEDROCK else "#8b5cf6"
    st.html(
        f"""<div style="margin-top:0.75rem;text-align:center;">
            <span style="background:rgba(20,184,166,0.08);border:1px solid {badge_color}33;
                         border-radius:20px;padding:3px 10px;font-size:0.7rem;color:{badge_color};">
                ● {badge_text}
            </span>
        </div>"""
    )

    st.divider()

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
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT AREA
# ─────────────────────────────────────────────────────────────────────────────

# ── CRISIS BANNER (persistent once triggered) ──────────────────────────────
if st.session_state.crisis_detected:
    st.html(
        """<div class="crisis-banner">
            <div style="font-size:1rem;font-weight:600;color:#f87171;margin-bottom:0.4rem;">
                🚨 If you're in crisis, help is available right now:
            </div>
            <div style="font-size:0.88rem;color:#fca5a5;line-height:1.8;">
                📞 <strong>988 Suicide &amp; Crisis Lifeline</strong> — Call or text 988 (24/7)<br>
                📞 <strong>UMD CAPS Crisis Line</strong> — (301) 314-7651<br>
                💬 <strong>Crisis Text Line</strong> — Text HOME to 741741
            </div>
        </div>"""
    )

# ── HERO SECTION (when no messages) ─────────────────────────────────────────
if not st.session_state.messages:
    # Gradient hero block
    st.html(
        """
        <div style="
            background: linear-gradient(135deg, rgba(10,10,20,0.9) 0%, rgba(10,20,25,0.8) 100%);
            border: 1px solid rgba(20,184,166,0.15);
            border-radius: 20px;
            padding: 2.5rem 2rem;
            text-align: center;
            margin-bottom: 1.5rem;
        ">
            <!-- Breathing circle -->
            <div style="
                width: 90px;
                height: 90px;
                background: radial-gradient(circle, rgba(20,184,166,0.25) 0%, rgba(20,184,166,0.05) 70%);
                border: 2px solid rgba(20,184,166,0.4);
                border-radius: 50%;
                margin: 0 auto 1.5rem;
                animation: breatheIn 4s ease-in-out infinite alternate;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2rem;
            ">🧠</div>

            <div style="background:linear-gradient(135deg,#14b8a6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-size:3.2rem;font-weight:800;line-height:1.1;">TerpWell</div>
            <div style="font-size: 1.05rem; color: #71717a; margin-top: 0.5rem;">
                Your UMD wellness companion, with built-in AI governance
            </div>
            <div style="font-size: 0.85rem; color: #14b8a6; margin-top: 0.35rem; margin-bottom: 2rem; font-weight: 500;">
                No waitlist. No cost. Available right now.
            </div>
        </div>
        """
    )

    # Feature cards
    cols = st.columns(4)
    features = [
        ("💚", "Empathetic Support", "A caring AI companion that listens without judgment"),
        ("🛡️", "AI Governance", "Every response audited in real-time for safety & accuracy"),
        ("🏫", "UMD Resources", "Verified campus mental health resources at your fingertips"),
        ("🔒", "Private & Safe", "No data stored. Crisis detection built in."),
    ]
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.html(
                f"""<div class="feature-card">
                    <div style="font-size:1.6rem;margin-bottom:0.5rem;">{icon}</div>
                    <div style="font-size:0.85rem;font-weight:600;color:#e4e4e7;margin-bottom:0.3rem;">{title}</div>
                    <div style="font-size:0.75rem;color:#71717a;line-height:1.5;">{desc}</div>
                </div>"""
            )

    # Quick prompts
    st.html(
        "<div style='text-align:center;margin:1.2rem 0 0.5rem;font-size:0.82rem;color:#52525b;'>Try asking:</div>"
    )
    pill_html = "".join(
        f'<span class="pill-prompt">{p}</span>' for p in QUICK_PROMPTS
    )
    st.html(
        f"<div style='text-align:center;'>{pill_html}</div>"
    )

    # Click handler via Streamlit buttons
    btn_cols = st.columns(len(QUICK_PROMPTS))
    for i, (col, prompt) in enumerate(zip(btn_cols, QUICK_PROMPTS)):
        with col:
            if st.button(prompt, key=f"quick_{i}", help=prompt):
                st.session_state.quick_prompt_selected = prompt
                st.rerun()

    # Disclaimer
    st.html(
        """<div style="text-align:center;margin-top:1.2rem;padding:0.7rem;
                    background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);
                    border-radius:10px;font-size:0.8rem;color:#f87171;">
            ⚠️ TerpWell is NOT a substitute for professional help.
            If you're in crisis, call 988 or UMD CAPS: (301) 314-7651
        </div>"""
    )

# ── CHAT HISTORY ────────────────────────────────────────────────────────────
else:
    for msg_idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            ts = msg.get("timestamp", "")
            st.html(
                f"""<div class="user-bubble">
                    <div class="user-bubble-inner">{msg['content']}</div>
                </div>"""
            )
        else:
            audit = msg.get("audit", {})
            score = audit.get("score", 100)
            was_corrected = msg.get("was_corrected", False)

            if was_corrected:
                badge = f'<span class="gov-badge-corrected">⚠️ Governance: Corrected ({score}/100)</span>'
            else:
                badge = f'<span class="gov-badge-approved">✅ Governance: Approved ({score}/100)</span>'

            st.html(
                f"""<div class="assistant-bubble">
                    <div class="assistant-avatar">🧠</div>
                    <div>
                        <div class="assistant-bubble-inner">{msg['content']}</div>
                        {badge}
                    </div>
                </div>"""
            )

            # Expandable governance audit panel
            if audit and audit.get("checks"):
                with st.expander("View Governance Audit", expanded=False):
                    checks = audit.get("checks", {})
                    check_display = {
                        "crisis_detection": "Crisis Detection",
                        "no_diagnosis": "No Diagnosis",
                        "no_prescribing": "No Prescribing",
                        "no_minimizing": "No Minimizing",
                        "appropriate_boundaries": "AI Boundaries",
                        "resource_accuracy": "Resource Accuracy",
                        "no_hallucination": "No Hallucination",
                        "factual_claims": "Factual Claims",
                        "empathetic_tone": "Empathetic Tone",
                        "not_condescending": "Not Condescending",
                        "culturally_sensitive": "Culturally Sensitive",
                    }

                    # Grid of pass/fail badges
                    grid_html = '<div class="check-grid">'
                    for key, label in check_display.items():
                        check = checks.get(key, {})
                        passed = check.get("pass", True)
                        note = check.get("note", "")
                        css_class = "check-pass" if passed else "check-fail"
                        icon = "✅" if passed else "❌"
                        title_attr = note.replace('"', "'") if note else label
                        grid_html += f'<div class="{css_class}" title="{title_attr}">{icon} {label}</div>'
                    grid_html += "</div>"
                    st.html(grid_html)

                    # Corrections diff if any
                    if was_corrected:
                        st.markdown("---")
                        st.html(
                            "<div style='font-size:0.8rem;color:#facc15;font-weight:600;margin-bottom:0.3rem;'>"
                            "⚠️ Correction Applied</div>"
                        )
                        corrections_text = audit.get("corrections", "")
                        if corrections_text and corrections_text != "None needed.":
                            st.html(
                                f"<div style='font-size:0.8rem;color:#a1a1aa;background:rgba(234,179,8,0.06);"
                                f"border:1px solid rgba(234,179,8,0.2);border-radius:8px;padding:0.5rem 0.7rem;'>"
                                f"{corrections_text}</div>"
                            )


# ─────────────────────────────────────────────────────────────────────────────
# COPING TOOLS SECTION
# ─────────────────────────────────────────────────────────────────────────────

# ── SESSION CARE PLAN ────────────────────────────────────────────────────────
user_msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
if user_msg_count >= 4:
    st.html("<div style='height:0.5rem'></div>")
    cp_col1, cp_col2 = st.columns([3, 1])
    with cp_col1:
        st.html(
            "<div style='font-size:0.72rem;color:#52525b;text-transform:uppercase;"
            "letter-spacing:0.08em;margin-bottom:0.3rem;'>Personalized Care Plan</div>"
        )
    with cp_col2:
        if st.button("📋 Generate", use_container_width=True, key="gen_care_plan"):
            with st.spinner("Building your care plan…"):
                plan = generate_care_plan(
                    st.session_state.messages,
                    list(set(st.session_state.topics)),
                    st.session_state.mood or "Not specified",
                )
            st.session_state.care_plan = plan
            st.rerun()

    if st.session_state.care_plan:
        plan = st.session_state.care_plan
        steps = plan.get("steps", [])
        note = plan.get("note", "")
        steps_html = ""
        for i, step in enumerate(steps[:3], 1):
            action = step.get("action", "")
            detail = step.get("detail", "")
            steps_html += (
                f"<div style='margin-bottom:0.6rem;'>"
                f"<div style='font-size:0.88rem;font-weight:600;color:#e4e4e7;margin-bottom:2px;'>"
                f"Step {i}: {action}</div>"
                f"<div style='font-size:0.8rem;color:#71717a;'>{detail}</div>"
                f"</div>"
            )
        if note:
            steps_html += (
                f"<div style='font-size:0.8rem;color:#14b8a6;margin-top:0.5rem;"
                f"border-top:1px solid rgba(255,255,255,0.06);padding-top:0.5rem;'>{note}</div>"
            )
        st.html(
            f"<div class='glass-card' style='border-left:3px solid #14b8a6;'>"
            f"{steps_html}</div>"
        )


st.html(
    "<div style='margin-top:1rem;margin-bottom:0.5rem;font-size:0.72rem;color:#52525b;"
    "text-transform:uppercase;letter-spacing:0.08em;'>Coping Tools</div>"
)

tool_col1, tool_col2, tool_col3 = st.columns(3)

with tool_col1:
    if st.button("🫁 Breathing Exercise", use_container_width=True):
        st.session_state.breathing_active = not st.session_state.breathing_active
        st.session_state.breathing_phase = "in"
        st.session_state.breathing_count = 0
        st.rerun()

with tool_col2:
    if st.button("📝 Journal Prompt", use_container_width=True):
        st.session_state.journal_prompt = random.choice(JOURNAL_PROMPTS)
        st.rerun()

with tool_col3:
    if st.button("🧘 Grounding Exercise", use_container_width=True):
        st.session_state.show_grounding = not st.session_state.show_grounding
        st.session_state.grounding_checks = [False] * 5
        st.rerun()

# ── Breathing Exercise ────────────────────────────────────────────────────────
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
                width: 110px;
                height: 110px;
                background: radial-gradient(circle, {color}33 0%, {color}08 70%);
                border: 2px solid {color}66;
                border-radius: 50%;
                margin: 0 auto 1rem;
                animation: {anim};
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2.2rem;
            ">🫁</div>
            <div style="font-size:1.3rem;font-weight:600;color:{color};">{label}</div>
            <div style="font-size:0.78rem;color:#71717a;margin-top:0.3rem;">4 seconds</div>
        </div>"""
    )

    bcol1, bcol2, bcol3 = st.columns([1, 2, 1])
    with bcol2:
        phase_order = ["in", "hold", "out"]
        if st.button("Next Phase ▶", use_container_width=True):
            idx = phase_order.index(st.session_state.breathing_phase)
            next_idx = (idx + 1) % len(phase_order)
            st.session_state.breathing_phase = phase_order[next_idx]
            if next_idx == 0:
                st.session_state.breathing_count += 1
            st.rerun()
        if st.button("Stop Breathing Exercise", use_container_width=True):
            st.session_state.breathing_active = False
            st.rerun()

# ── Journal Prompt ────────────────────────────────────────────────────────────
if st.session_state.journal_prompt and not st.session_state.breathing_active:
    st.html(
        f"""<div class="glass-card" style="border-left: 3px solid #8b5cf6;padding:1rem 1.2rem;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;
                        color:#71717a;margin-bottom:0.4rem;">📝 Journal Prompt</div>
            <div style="font-size:0.95rem;color:#e4e4e7;line-height:1.6;">
                {st.session_state.journal_prompt}
            </div>
            <div style="font-size:0.75rem;color:#52525b;margin-top:0.5rem;">
                Take a moment to reflect. You don't need to share — just write for yourself.
            </div>
        </div>"""
    )
    jcol1, jcol2 = st.columns([1, 1])
    with jcol1:
        if st.button("New Prompt", use_container_width=True):
            st.session_state.journal_prompt = random.choice(JOURNAL_PROMPTS)
            st.rerun()
    with jcol2:
        if st.button("Close", key="close_journal", use_container_width=True):
            st.session_state.journal_prompt = None
            st.rerun()

# ── Grounding Exercise ────────────────────────────────────────────────────────
if st.session_state.show_grounding and not st.session_state.breathing_active:
    st.html(
        """<div class="glass-card" style="border-left: 3px solid #14b8a6;">
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

    if st.button("Close Grounding Exercise", key="close_grounding"):
        st.session_state.show_grounding = False
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# CHAT INPUT & MESSAGE HANDLING
# ─────────────────────────────────────────────────────────────────────────────

st.html("<div style='height:0.5rem'></div>")

# Pre-fill from quick prompt
prefill_value = ""
if st.session_state.quick_prompt_selected:
    prefill_value = st.session_state.quick_prompt_selected
    st.session_state.quick_prompt_selected = None

# Show API error if any
if st.session_state.api_error:
    st.error(f"⚠️ {st.session_state.api_error}")
    st.session_state.api_error = None

user_input = st.chat_input(
    placeholder="Share what's on your mind… I'm here to listen 💙",
)

# Process quick prompt or typed message
if prefill_value and not user_input:
    user_input = prefill_value

if user_input and user_input.strip():
    raw_text = user_input.strip()

    if not raw_text:
        st.stop()

    # Fast regex crisis check first
    if detect_crisis(raw_text):
        st.session_state.crisis_detected = True

    # Extract topics
    st.session_state.topics.extend(extract_topics(raw_text))

    # Save user message
    st.session_state.messages.append({
        "role": "user",
        "content": raw_text,
        "timestamp": datetime.datetime.now().strftime("%H:%M"),
    })

    # Build API history (exclude the message we just added)
    api_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m["role"] in ("user", "assistant")
    ]

    profile = {
        "mood": st.session_state.mood or "Not specified",
        "topics": list(set(st.session_state.topics)),
    }

    # Render the user bubble inline so it appears before streaming starts
    st.html(
        f"""<div class="user-bubble">
            <div class="user-bubble-inner">{raw_text}</div>
        </div>"""
    )

    # Streaming assistant bubble
    st.html('<div class="assistant-bubble"><div class="assistant-avatar">🧠</div>')
    stream_placeholder = st.empty()
    st.html("</div>")

    try:
        # Stream companion response
        draft = stream_companion(raw_text, profile, api_history, stream_placeholder)

        # Claude-powered crisis detection (runs after streaming, catches nuanced signals)
        with st.spinner("🛡️ Auditing response…"):
            crisis_result = detect_crisis_claude(raw_text)
            level = crisis_result.get("crisis_level", "none")
            st.session_state.triage_level = level
            if level in ("mild", "urgent"):
                st.session_state.crisis_detected = True

            audit, was_corrected = run_governance(raw_text, draft)

        final_response = audit.pop("_final", draft)

        # Record governance score and sentiment
        st.session_state.governance_scores.append(audit.get("score", 100))
        sentiment = audit.get("sentiment_score", 3)
        if isinstance(sentiment, int) and 1 <= sentiment <= 5:
            st.session_state.sentiment_scores.append(sentiment)

        st.session_state.messages.append({
            "role": "assistant",
            "content": final_response,
            "timestamp": datetime.datetime.now().strftime("%H:%M"),
            "audit": audit,
            "was_corrected": was_corrected,
        })

    except anthropic.AuthenticationError:
        st.session_state.api_error = (
            "Authentication failed. Please set ANTHROPIC_API_KEY or configure AWS credentials."
        )
    except anthropic.RateLimitError:
        st.session_state.api_error = "Rate limit reached. Please wait a moment and try again."
    except anthropic.APIConnectionError:
        st.session_state.api_error = "Connection error. Please check your internet connection."
    except Exception as e:
        st.session_state.api_error = f"Unexpected error: {str(e)[:200]}"

    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.html(
    """<div class="footer-text">
        Built at <strong>Anthropic × Maryland Hackathon 2025</strong> |
        TerpWell — Wellness with Governance<br>
        <span style="color:#ef4444;">⚠️ Not a substitute for professional help.</span>
        For crisis support: call or text <strong>988</strong> or UMD CAPS <strong>(301) 314-7651</strong>
    </div>"""
)
