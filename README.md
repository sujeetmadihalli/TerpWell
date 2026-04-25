# 🐢 TerpWell

**Mental health support you can trust. Every response verified.**

TerpWell is an AI wellness companion built for University of Maryland students, featuring a real-time AI governance layer that audits every response before it reaches the user.

Built at the **Anthropic x Maryland Hackathon 2025**.

---

## The Problem

1 in 3 college students experience significant anxiety or depression, yet most never reach out to campus resources. Existing AI chatbots hallucinate hotline numbers, overstep clinical boundaries, and sometimes minimize feelings. Students need an always-available first touchpoint they can actually trust.

## The Solution

TerpWell uses a **two-layer architecture**:

```
Student Message
      |
[Crisis Detection] --> regex + Claude classifier
      |
[Companion AI] --> Empathetic streaming response
      |
[Governance AI] --> 7-check safety audit
      |
  Approved? --> Show with "Verified" badge
  Failed?   --> Auto-correct --> Show with "Reviewed" badge
```

Every single response is audited against 7 checks before the student sees it:
1. **Crisis Detection** - crisis mentions get resources
2. **No Diagnosis** - never diagnoses conditions
3. **No Prescribing** - never recommends medication
4. **No Minimizing** - never dismisses feelings
5. **Resource Accuracy** - phone numbers verified correct
6. **No Hallucination** - no fake resources or organizations
7. **Empathetic Tone** - warm and validating

## Features

### Empathetic Chat
- Streaming responses that sound like a real UMD student, not a clinical bot
- Knows real campus spots: Lake Artemesia, Board & Brew, CAPS in Shoemaker, RecWell climbing wall
- Validates feelings first, asks follow-up questions, one suggestion at a time

### AI Governance (Invisible)
- Runs silently on every response
- Small "Verified" or "Reviewed" badge is the only visible indicator
- Failed responses are automatically corrected before delivery
- Catches hallucinated resources, clinical overstepping, minimizing language

### Dual-Layer Crisis Detection
- **Regex layer**: instant keyword matching for direct crisis language
- **Claude layer**: semantic classification catching indirect language ("I don't see the point anymore")
- Immediately surfaces verified 988, CAPS, and Crisis Text Line resources

### Mood Tracker
- Log mood with emoji + notes throughout the day
- 30-day timeline with rolling average (Plotly)
- Weekly averages, mood distribution, day-of-week patterns
- Mood history fed into Claude's context for personalized responses

### Login & Persistence
- SQLite database storing users, mood entries, chat sessions, messages
- Persistent chat history and mood data across sessions
- Demo user pre-seeded with 30 days of realistic college mood data

### Human Escalation
- Generates structured handoff messages for CAPS counselors
- Session export as markdown for sharing with therapists
- Neurodivergent support with verified ADS and ADHD coaching resources

## Screenshots

| Login | Chat | Mood Dashboard |
|-------|------|----------------|
| Clean centered login | iOS-style dark chat with governance badges | Plotly charts with 30-day data |

## Quick Start

### Prerequisites
- Python 3.10+
- AWS Bedrock access (or Anthropic API key)

### Install
```bash
git clone git@github.com:sujeetmadihalli/TerpWell.git
cd TerpWell
pip install streamlit anthropic plotly pandas
```

### Run
```bash
# With AWS Bedrock (auto-detected)
streamlit run app.py

# With Anthropic API key
ANTHROPIC_API_KEY=your_key streamlit run app.py
```

### Demo Login
- **Username:** `testterp`
- **Password:** `terp2026`

The test user comes with 30 days of pre-seeded mood data showing realistic college patterns (midterm stress dip, weekend recovery).

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit 1.56, Custom HTML/CSS |
| AI | Claude Sonnet 4.6 (via AWS Bedrock) |
| Database | SQLite with WAL journaling |
| Visualization | Plotly |
| Data | Pandas |
| SDK | Anthropic Python SDK |

## Architecture

```
app.py (single file, ~1780 lines)
├── Database Layer (SQLite)
│   ├── users, mood_entries, chat_sessions, chat_messages
│   └── 30-day seed data generator
├── AI Layer
│   ├── Companion AI (streaming, UMD-specific personality)
│   ├── Governance AI (7-check JSON audit)
│   ├── Crisis Detection (regex + Claude classifier)
│   └── Care Plan / Escalation generators
├── UI Layer
│   ├── Login Screen
│   ├── Chat Screen (iOS dark theme)
│   └── Mood Dashboard (4 Plotly charts)
└── Resources (verified UMD phone numbers)
```

## Verified UMD Resources

All resources are hardcoded and verified. The governance layer rejects any response containing incorrect numbers.

| Resource | Contact |
|----------|---------|
| 988 Suicide & Crisis Lifeline | Call or text 988 (24/7) |
| UMD CAPS (Counseling) | (301) 314-7651 |
| Crisis Text Line | Text HOME to 741741 |
| UMD Health Center | (301) 314-8180 |
| Campus Police | 911 or (301) 405-3333 |
| CARE to Stop Violence | (301) 314-2222 |
| Dean of Students | (301) 314-8783 |
| Accessibility & Disability Service | (301) 314-7682 |

## Future Roadmap

- University SSO via UMD CAS for real student profiles
- Voice interface using Web Speech API
- Therapist dashboard for CAPS counselors
- Push notifications for mood check-in reminders
- Multi-university deployment with configurable resources
- Predictive mood analytics using time series models

## Team

Built at the Anthropic x Maryland Hackathon 2025 by UMD students.

## Disclaimer

TerpWell is **not** a substitute for professional help. If you're in crisis, call **988** or UMD CAPS: **(301) 314-7651**.
