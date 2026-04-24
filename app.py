"""
TerpWell — UMD Wellness Companion
Clean mobile-first redesign with two-layer AI governance.
"""

import os, json, time, re, random, datetime
import streamlit as st
import anthropic

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

def companion_prompt(mood):
    return f"""You are TerpWell — think of yourself as a caring older student at the University of Maryland who's been through it all. You talk like a real person, not a chatbot. You use casual language, contractions, and you're genuinely warm. You're NOT a therapist, counselor, or medical professional — you're a supportive friend who happens to know every resource on campus.

## Your Personality:
- You speak naturally: "hey", "honestly", "I totally get that", "that sounds really rough"
- You share relatable observations: "midterm season at UMD is no joke" not "exam periods can be stressful"
- You're specific to UMD — you mention real places, real experiences, real campus life
- You ask thoughtful follow-up questions, don't just give advice
- You validate before suggesting — always acknowledge their feelings first
- One suggestion at a time, not a laundry list
- Keep it to 2-3 short paragraphs max

## UMD-Specific Knowledge:
When relevant, naturally weave in real UMD places and suggestions:

RELAXATION & NATURE:
- Lake Artemesia — peaceful walk, only 10 min from campus
- The Garden of Reflection near the Chapel — quiet meditation spot
- Paint Branch Trail — great for clearing your head with a run or walk
- McKeldin Mall — sit on the grass, people-watch, decompress between classes
- Clarice Smith Performing Arts Center — free concerts and performances

FOOD & COMFORT:
- The Diner (open late) — comfort food when you need it at 1am
- Board & Brew on Route 1 — chill board game cafe, great for socializing
- Vigilante Coffee in Hyattsville — cozy off-campus study spot
- College Park farmers market (Saturdays) — nice way to get outside

SOCIAL & COMMUNITY:
- UMD RecWell — group fitness classes, rock climbing wall at Eppley
- Stamp Student Union — game room, events, just a good place to hang
- 400+ student orgs — there's literally a club for everything
- Intramural sports — low-pressure way to move your body and meet people
- Terrapin Trail Club — hiking trips to get off campus

ACADEMIC SUPPORT:
- Tutoring at the Learning Assistance Service in Shoemaker
- Writing Center in Tawes Hall — help with papers
- Academic Success & Tutorial Services
- Each college has its own advising office

MINDFULNESS & WELLNESS:
- UMD RecWell offers free yoga and meditation classes
- Mindfulness Room in the Stamp Student Union
- Health Center has wellness workshops throughout the semester

NEURODIVERGENT SUPPORT:
- Accessibility & Disability Service (ADS): (301) 314-7682, ads.umd.edu — ADHD, learning disabilities, autism support, free for registered students
- ADHD/LD Coaching: through ADS, free for registered students, ads.umd.edu/services/coaching
- If you're struggling in class and think ADHD or a learning difference might be involved, ADS is genuinely helpful and low-barrier to access

## Crisis Protocol:
If the user mentions suicide, self-harm, wanting to die, or immediate danger, drop everything and respond with empathy + these exact resources:
"I'm really glad you told me this. You don't have to go through this alone. Please reach out right now:
- **988 Suicide & Crisis Lifeline** — Call or text 988 (24/7, free)
- **UMD CAPS Crisis Line** — (301) 314-7651 (press 1 after hours)
- **Crisis Text Line** — Text HOME to 741741
These are real people who care and are trained to help. Can I help you take that step?"

## Verified UMD Resources (use ONLY these — never make up resources):
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

## Rules:
- Be a human, not a helpline script
- Reference specific UMD places, not generic "go outside" or "try meditation"
- If someone mentions a specific situation (roommate issues, academic stress, loneliness), ask follow-up questions before jumping to solutions
- When suggesting professional help, normalize it: "tons of Terps use CAPS — it's literally free and right in Shoemaker"
- Never say "I'm just an AI" unprompted — only clarify your limitations if directly asked or if the situation requires professional help
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
7. EMPATHETIC_TONE: Must be warm, human, and validating — not robotic or clinical

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

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=companion_prompt(mood),
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
    "show_mood_log": False,
    "mood_log": [],
    "topics": [],
    "triage_level": "none",
    "care_plan": None,
    "api_error": None,
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
/* Header buttons override — make circular */
[data-testid="stHorizontalBlock"]:first-of-type .stButton > button {
    border-radius: 50% !important;
    padding: 6px !important;
    min-height: 38px !important;
    width: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #1a1a1a !important;
    border: 1px solid #2a2a2a !important;
    font-size: 1rem !important;
}
[data-testid="stHorizontalBlock"]:first-of-type .stButton > button:hover {
    border-color: #0a84ff !important;
    background: rgba(10,132,255,0.08) !important;
}

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
</style>""")

# ── HEADER ─────────────────────────────────────────────────────────────────────

mood_display = f" · {st.session_state.mood}" if st.session_state.mood else ""

hdr_left, hdr_center, hdr_right = st.columns([0.15, 0.70, 0.15], gap="small")
with hdr_left:
    if st.button("📊", key="mood_log_toggle", use_container_width=False):
        st.session_state.show_mood_log = not st.session_state.show_mood_log
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
        st.session_state.show_mood_log = False
        st.rerun()

st.html('<div style="border-bottom:1px solid #1a1a1a;margin-bottom:12px;"></div>')

# ── RESOURCES PANEL ────────────────────────────────────────────────────────────

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

# ── MOOD LOG PANEL ────────────────────────────────────────────────────────────

if st.session_state.show_mood_log:
    mood_log = st.session_state.mood_log

    st.html('<div class="resources-panel"><div class="resources-panel-title">Mood Tracker</div>')
    log_cols = st.columns([0.6, 0.4])
    with log_cols[0]:
        mood_note = st.text_input("How are you feeling right now?", key="mood_note_input", placeholder="Optional note...", label_visibility="collapsed")
    with log_cols[1]:
        mood_emojis = ["😢", "😟", "😐", "🙂", "😊"]
        m_cols = st.columns(5)
        for mi, (mc, me) in enumerate(zip(m_cols, mood_emojis)):
            with mc:
                if st.button(me, key=f"mlog_{mi}"):
                    st.session_state.mood = me
                    st.session_state.mood_log.append({
                        "time": time.time(),
                        "mood": me,
                        "note": mood_note or "",
                    })
                    st.rerun()

    if mood_log:
        mood_map = {"😢": 1, "😟": 2, "😐": 3, "🙂": 4, "😊": 5}
        mood_labels = {"😢": "Struggling", "😟": "Low", "😐": "Okay", "🙂": "Good", "😊": "Great"}

        recent = mood_log[-10:]
        dots_html = '<div style="display:flex;align-items:flex-end;gap:6px;margin:16px 0 12px;height:60px;">'
        for entry in recent:
            m = entry["mood"]
            h = mood_map.get(m, 3) * 12
            t = time.strftime("%I:%M", time.localtime(entry["time"])).lstrip("0")
            dots_html += f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;flex:1;">'
            dots_html += f'<div style="font-size:1.1rem;">{m}</div>'
            dots_html += f'<div style="width:4px;height:{h}px;background:{"#34c759" if mood_map.get(m,3)>=4 else "#ff9f0a" if mood_map.get(m,3)==3 else "#ff453a"};border-radius:2px;"></div>'
            dots_html += f'<div style="font-size:0.6rem;color:#555;">{t}</div>'
            dots_html += '</div>'
        dots_html += '</div>'
        st.html(dots_html)

        scores = [mood_map.get(e["mood"], 3) for e in mood_log]
        avg = sum(scores) / len(scores)
        avg_emoji = mood_emojis[min(4, max(0, round(avg) - 1))]
        st.html(f'<div style="display:flex;gap:24px;justify-content:center;margin:8px 0;font-size:0.78rem;color:#888;">'
                f'<span>Entries: <strong style="color:#ccc">{len(mood_log)}</strong></span>'
                f'<span>Average: <strong style="color:#ccc">{avg_emoji} {avg:.1f}/5</strong></span>'
                f'</div>')

        for entry in reversed(mood_log[-5:]):
            t = time.strftime("%I:%M %p", time.localtime(entry["time"])).lstrip("0")
            note = entry.get("note", "")
            note_html = f'<span style="color:#999;margin-left:8px;">{note}</span>' if note else ""
            label = mood_labels.get(entry["mood"], "")
            st.html(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid #1a1a1a;">'
                    f'<span style="font-size:0.75rem;color:#555;width:56px;">{t}</span>'
                    f'<span style="font-size:1.2rem;">{entry["mood"]}</span>'
                    f'<span style="font-size:0.8rem;color:#bbb;">{label}</span>'
                    f'{note_html}</div>')
    else:
        st.html('<div style="text-align:center;color:#555;font-size:0.82rem;padding:20px 0;">No mood entries yet. Tap an emoji above to log how you\'re feeling.</div>')

    st.html('</div>')

# ── CRISIS BANNER ──────────────────────────────────────────────────────────────

if st.session_state.crisis_detected:
    st.html("""<div class="crisis-card">
    <div class="crisis-title">If you're in crisis, help is available now</div>
    <div class="crisis-body">
        📞 988 Suicide &amp; Crisis Lifeline (call or text)<br>
        📞 UMD CAPS: (301) 314-7651<br>
        💬 Crisis Text Line: Text HOME to 741741
    </div>
</div>""")

# ── WELCOME SCREEN ─────────────────────────────────────────────────────────────

if not st.session_state.messages and not st.session_state.pending_prompt:
    st.html("""<div class="welcome-container">
    <div class="welcome-icon">🐢</div>
    <div class="welcome-title">Hey, Terp.</div>
    <div class="welcome-sub">How's your day going? I'm here to listen.</div>
</div>""")

    st.html('<div style="text-align:center;color:#666;font-size:0.82rem;margin:16px 0 8px;">How are you feeling?</div>')
    moods = ["😢", "😟", "😐", "🙂", "😊"]
    cols = st.columns(5)
    for i, (col, emoji) in enumerate(zip(cols, moods)):
        with col:
            if st.button(emoji, key=f"mood_{i}", use_container_width=True):
                st.session_state.mood = emoji
                st.session_state.mood_log.append({
                    "time": time.time(),
                    "mood": emoji,
                    "note": "",
                })
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

# ── CHAT MESSAGES ──────────────────────────────────────────────────────────────

elif st.session_state.messages:
    import html as html_mod

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

# ── STATUS PLACEHOLDER ─────────────────────────────────────────────────────────

status_ph = st.empty()

# ── INPUT HANDLING ─────────────────────────────────────────────────────────────

if st.session_state.pending_prompt:
    user_input = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
else:
    user_input = st.chat_input("What's on your mind?")

# ── PROCESS MESSAGE ────────────────────────────────────────────────────────────

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

    # Build API history (exclude the just-added user message)
    api_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m["role"] in ("user", "assistant")
    ]

    # Show user bubble inline so it appears before streaming
    import html as html_mod
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

            # Run governance AFTER streaming completes
            audit, was_corrected = run_governance(raw_text, draft)

        final_response = audit.pop("_final", draft)

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

# ── DISCLAIMER ─────────────────────────────────────────────────────────────────

st.html('<div class="disclaimer">TerpWell is not a substitute for professional help. If you\'re in crisis, call 988 or UMD CAPS: (301) 314-7651</div>')
