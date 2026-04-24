import streamlit as st
import requests
import pandas as pd
import re
import json
from datetime import datetime
from collections import Counter

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SME Voice Survey",
    page_icon="✦",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Lora:ital,wght@0,400;0,500;1,400&display=swap');
html, body, [class*="css"] { font-family: 'Lora', Georgia, serif; }
h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif !important; }
.step-label {
    font-family: 'Playfair Display', serif;
    font-size: 0.7em; letter-spacing: 0.15em;
    text-transform: uppercase; color: #c4a050;
}
.section-card {
    background: rgba(196,160,80,0.06);
    border: 1px solid rgba(196,160,80,0.25);
    border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 1rem;
}
.calibration-card {
    background: #f8f8f8;
    border: 2px solid transparent;
    border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    cursor: pointer;
}
.calibration-card.selected {
    border-color: #c4a050;
    background: rgba(196,160,80,0.08);
}
</style>
""", unsafe_allow_html=True)

# ── Airtable ───────────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = st.secrets["airtable"]["token"]
AIRTABLE_BASE  = st.secrets["airtable"]["base_id"]
AIRTABLE_TABLE = st.secrets["airtable"]["table_name"]
AIRTABLE_URL   = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}"
HEADERS        = {"Authorization": f"Bearer {AIRTABLE_TOKEN}",
                  "Content-Type": "application/json"}

def save_response(data: dict):
    style  = data["style_answers"]
    cal    = data["calibration"]
    nlp    = data["nlp_metrics"]
    fields = {
        "Timestamp":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "First Name":         data.get("first_name", ""),
        "Last Name":          data.get("last_name", ""),
        "Title":              data.get("title", ""),
        "Department":         data.get("department", ""),
        "Email":              data.get("email", ""),
        "Years Experience":   data.get("years_experience", ""),
        # Style sliders
        "Tone":               style.get("tone", ""),
        "Complexity":         style.get("complexity", ""),
        "Sentence Length":    style.get("sentence_length", ""),
        "Jargon":             style.get("jargon", ""),
        "Contrarian":         style.get("contrarian", ""),
        # Style choices
        "Structure":          style.get("structure", ""),
        "Perspective":        style.get("perspective", ""),
        "Hooks":              style.get("hooks", ""),
        "Closing":            style.get("closing", ""),
        "Evidence":           ", ".join(style.get("evidence", [])),
        # Calibration
        "Calibration Tone":       cal.get("tone_example", ""),
        "Calibration Structure":  cal.get("structure_example", ""),
        "Calibration Opening":    cal.get("opening_example", ""),
        # Writing samples
        "Writing Sample 1":   data["writing_samples"][0],
        "Writing Sample 2":   data["writing_samples"][1],
        "Writing Sample 3":   data["writing_samples"][2],
        # NLP metrics (stored as JSON string)
        "NLP Metrics":        json.dumps(nlp),
        # Generated prompt
        "AI Prompt":          data.get("ai_prompt", ""),
    }
    fields = {k: v for k, v in fields.items() if v not in ["", None, "{}"]}
    resp = requests.post(AIRTABLE_URL, headers=HEADERS, json={"fields": fields})
    resp.raise_for_status()

def load_all_responses():
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        resp = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([{"id": r["id"], **r["fields"]} for r in records])

# ── NLP Analysis ───────────────────────────────────────────────────────────────
STOPWORDS = set("""a an the and or but in on at to for of with as is are was were
    be been being have has had do does did will would could should may might
    i me my we our you your he she it its they them their this that these those
    not no nor so yet both either neither just also very really quite""".split())

PASSIVE_PATTERN = re.compile(
    r'\b(was|were|is|are|been|being|be)\s+\w+ed\b', re.IGNORECASE
)

def analyse_text(samples: list) -> dict:
    combined = " ".join(s for s in samples if s.strip())
    if not combined or len(combined.split()) < 30:
        return {}

    try:
        import textstat
        flesch    = textstat.flesch_reading_ease(combined)
        fk_grade  = textstat.flesch_kincaid_grade(combined)
        readability = textstat.text_standard(combined, float_output=False)
    except Exception:
        flesch, fk_grade, readability = None, None, None

    # Sentence metrics
    sentences = re.split(r'[.!?]+', combined)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) > 2]
    avg_sent_len = round(sum(len(s.split()) for s in sentences) / len(sentences), 1) if sentences else 0

    # Word metrics
    words = re.findall(r'\b[a-zA-Z]+\b', combined.lower())
    total_words = len(words)
    unique_words = len(set(words))
    lexical_diversity = round(unique_words / total_words, 3) if total_words else 0

    # Distinctive words (non-stopword, 5+ chars, appears 2+ times)
    content_words = [w for w in words if w not in STOPWORDS and len(w) >= 5]
    top_words = [w for w, _ in Counter(content_words).most_common(15)]

    # Passive voice
    passive_count = len(PASSIVE_PATTERN.findall(combined))
    passive_ratio = round(passive_count / len(sentences), 2) if sentences else 0

    # First person
    first_person = len(re.findall(r'\b(I|me|my|we|our)\b', combined))
    first_person_ratio = round(first_person / total_words * 100, 1) if total_words else 0

    # Questions
    question_count = combined.count("?")

    # Em-dashes and parentheticals
    em_dashes = combined.count("—") + combined.count("--")
    parentheticals = len(re.findall(r'\(.*?\)', combined))

    return {
        "total_words": total_words,
        "avg_sentence_length": avg_sent_len,
        "lexical_diversity": lexical_diversity,
        "flesch_reading_ease": flesch,
        "flesch_kincaid_grade": fk_grade,
        "readability_level": readability,
        "passive_voice_per_sentence": passive_ratio,
        "first_person_pct": first_person_ratio,
        "question_count": question_count,
        "em_dashes": em_dashes,
        "parentheticals": parentheticals,
        "distinctive_words": top_words,
    }

# ── Prompt Builder ─────────────────────────────────────────────────────────────
def build_prompt(data: dict, nlp: dict) -> str:
    s = data["style_answers"]
    c = data["calibration"]
    name = f"{data.get('first_name','')} {data.get('last_name','')}".strip()
    samples = [x for x in data["writing_samples"] if x.strip()]

    tone_desc = {1:"highly formal and authoritative", 2:"formal with occasional warmth",
                 3:"balanced", 4:"approachable with professional grounding",
                 5:"conversational and direct"}.get(s.get("tone",3),"balanced")
    jargon_desc = {1:"avoid all jargon", 2:"minimal jargon", 3:"moderate jargon",
                   4:"use jargon freely", 5:"heavy use of technical terminology"
                   }.get(s.get("jargon",3),"moderate jargon")
    contrarian_desc = {1:"stay close to consensus", 2:"gently nuanced",
                       3:"occasionally challenge the consensus",
                       4:"actively challenge conventional wisdom",
                       5:"deliberately provocative and contrarian"
                       }.get(s.get("contrarian",3),"occasionally challenge the consensus")

    nlp_notes = []
    if nlp.get("avg_sentence_length"):
        nlp_notes.append(f"- Average sentence length: {nlp['avg_sentence_length']} words")
    if nlp.get("passive_voice_per_sentence") is not None:
        pv = nlp["passive_voice_per_sentence"]
        nlp_notes.append(f"- Passive voice: {'rarely used' if pv < 0.1 else 'occasionally used' if pv < 0.3 else 'frequently used'} ({pv} per sentence)")
    if nlp.get("first_person_pct"):
        nlp_notes.append(f"- First person usage: {nlp['first_person_pct']}% of words")
    if nlp.get("em_dashes"):
        nlp_notes.append(f"- Uses em-dashes for asides: {nlp['em_dashes']} instances")
    if nlp.get("parentheticals"):
        nlp_notes.append(f"- Uses parentheticals: {nlp['parentheticals']} instances")
    if nlp.get("distinctive_words"):
        nlp_notes.append(f"- Recurring vocabulary: {', '.join(nlp['distinctive_words'][:8])}")
    if nlp.get("readability_level"):
        nlp_notes.append(f"- Readability level: {nlp['readability_level']}")

    sample_block = "\n\n".join(f'"{s}"' for s in samples[:2]) if samples else "(no samples provided)"

    prompt = f"""You are ghostwriting an opinion editorial on behalf of {name}, a senior professional with {data.get('years_experience','extensive')} experience in financial services.

Write in their voice exactly as described below. Do not soften arguments. Do not add unnecessary caveats. Write as this person would write.

## Voice Profile — Self-Reported

**Tone:** {tone_desc}
**Sentence style:** {'Short and punchy' if s.get('sentence_length',3) <= 2 else 'Flowing and layered' if s.get('sentence_length',3) >= 4 else 'Varied sentence length'}
**Jargon:** {jargon_desc}
**Technical complexity:** {'Assume expert audience — do not over-explain' if s.get('complexity',3) <= 2 else 'Explain concepts accessibly' if s.get('complexity',3) >= 4 else 'Balanced — brief explanations where needed'}
**Contrarian stance:** {contrarian_desc}
**Argument structure:** {s.get('structure', 'Lead with insight, then support')}
**Perspective:** {s.get('perspective', 'First person')}
**Opening style:** {s.get('hooks', 'Bold statement')}
**Closing style:** {s.get('closing', 'Forward-looking')}
**Evidence style:** {', '.join(s.get('evidence', [])) or 'Mixed'}

## Voice Profile — Calibration (chosen by SME)

**Tone example they identified with:** {c.get('tone_example', 'not provided')}
**Structure example they identified with:** {c.get('structure_example', 'not provided')}
**Opening example they identified with:** {c.get('opening_example', 'not provided')}

## Voice Profile — Objective Analysis (extracted from writing samples)
{"chr(10).join(nlp_notes) if nlp_notes else 'Insufficient sample text for analysis.'}

## Writing Samples (their actual voice)
{sample_block}

## Task
Write a 600-word op-ed on the following topic:

{{TOPIC}}

Replicate the voice above precisely. Pay particular attention to sentence length, how they open their argument, and their comfort with provocation."""

    return prompt

# ── Survey Content ─────────────────────────────────────────────────────────────
STYLE_QUESTIONS = [
    {"id": "tone", "type": "scale",
     "question": "How would you describe your natural writing tone?",
     "left": "Formal & authoritative", "right": "Conversational & approachable"},
    {"id": "complexity", "type": "scale",
     "question": "How do you handle complex concepts for your audience?",
     "left": "Technical depth, assume expertise", "right": "Plain language, always explain"},
    {"id": "sentence_length", "type": "scale",
     "question": "What's your natural sentence style?",
     "left": "Short, punchy sentences", "right": "Longer, flowing constructions"},
    {"id": "jargon", "type": "scale",
     "question": "Your relationship with industry jargon?",
     "left": "Avoid it entirely", "right": "Use it freely — it's precise"},
    {"id": "contrarian", "type": "scale",
     "question": "How comfortable are you taking a contrarian position?",
     "left": "I prefer measured consensus views", "right": "I actively challenge conventional wisdom"},
    {"id": "structure", "type": "radio",
     "question": "What's your preferred argument structure?",
     "options": [
         "Lead with the headline insight, then support it",
         "Build the argument methodically to a conclusion",
         "Tell a story that carries the reader to the point",
         "Present balanced perspectives, then my view",
     ]},
    {"id": "perspective", "type": "radio",
     "question": "How do you position yourself in your writing?",
     "options": [
         "Strong personal voice — 'I think…', 'In my view…'",
         "Institutional voice — 'The data shows…', 'Our research suggests…'",
         "Detached analyst — let the evidence speak",
         "Collaborative — 'We are seeing…', 'Our clients…'",
     ]},
    {"id": "hooks", "type": "radio",
     "question": "How do you typically open a piece?",
     "options": [
         "A bold, provocative statement",
         "A surprising statistic or fact",
         "A question that reframes the issue",
         "A brief anecdote or scene-setting",
         "Context and background first",
     ]},
    {"id": "closing", "type": "radio",
     "question": "How do your pieces typically end?",
     "options": [
         "A clear call to action or recommendation",
         "A forward-looking outlook or prediction",
         "A thought-provoking open question",
         "A summary that reinforces the core point",
     ]},
    {"id": "evidence", "type": "multiselect",
     "question": "How do you typically back up your arguments? (select all that apply)",
     "options": [
         "Data and statistics", "Real-world case studies",
         "Historical analogies", "Expert citations",
         "Personal experience", "First principles reasoning",
     ]},
]

# Calibration examples — 3 sets of 3 paragraphs each representing different styles
CALIBRATION = {
    "tone": {
        "label": "Tone & voice",
        "question": "Which of these most closely matches how you naturally write?",
        "options": [
            {
                "id": "formal",
                "label": "Option A",
                "text": "The correlation between central bank communication and equity market volatility has been well-documented in the academic literature. What remains underappreciated, however, is the asymmetric nature of this relationship — markets respond more sharply to hawkish surprises than to dovish ones, a pattern that has meaningful implications for portfolio construction."
            },
            {
                "id": "balanced",
                "label": "Option B",
                "text": "Central banks have more power over markets than many investors realise — not just through what they do, but through what they say. I've watched portfolios get blindsided by a single word change in a policy statement. The lesson? Read the language, not just the numbers."
            },
            {
                "id": "conversational",
                "label": "Option C",
                "text": "Here's the thing about central banks nobody tells you: they're mostly just making it up as they go. That sounds cynical, but it's actually liberating. If the RBA doesn't have a perfect model, you don't need one either. You just need to be slightly less wrong than everyone else."
            },
        ]
    },
    "structure": {
        "label": "Argument structure",
        "question": "Which approach best describes how you build an argument?",
        "options": [
            {
                "id": "deductive",
                "label": "Option A",
                "text": "Australian equities are structurally undervalued relative to global peers. Three factors explain this discount: an overconcentration in financials and resources, a domestic investor base with mandated offshore diversification, and a persistent underrepresentation in global indices. Each is addressable. None has been."
            },
            {
                "id": "narrative",
                "label": "Option B",
                "text": "In 2018, a client asked me why we were still holding a position that had underperformed for two years. I told them: because the thesis hadn't changed, only the timeline had. Eighteen months later that position was our best performer for the decade. Patience isn't passive — it's a strategy."
            },
            {
                "id": "inductive",
                "label": "Option C",
                "text": "Consider what happened to bond markets in 2022. Then look at what happened to 60/40 portfolios. Then consider how many retail investors were told that diversification would protect them. By the time you've traced that chain, the conclusion writes itself: the model was always fragile."
            },
        ]
    },
    "opening": {
        "label": "Opening style",
        "question": "Which opening feels most natural to you?",
        "options": [
            {
                "id": "provocative",
                "label": "Option A",
                "text": "The passive investing boom is the most dangerous idea in modern finance — and nobody wants to say it out loud."
            },
            {
                "id": "data_led",
                "label": "Option B",
                "text": "In the twelve months to September, passive funds absorbed 73% of net equity inflows globally. That number deserves more attention than it's getting."
            },
            {
                "id": "contextual",
                "label": "Option C",
                "text": "For most of the twentieth century, beating the market was considered the basic job description of a fund manager. That assumption has been quietly dismantled over the past two decades, with consequences we're only beginning to understand."
            },
        ]
    },
}

WRITING_PROMPTS = [
    ("Existing writing sample",
     "Paste a recent LinkedIn post, article excerpt, email, or internal brief you've written (any length — the more the better)."),
    ("Your view right now",
     "Pick any topic in your field and write 3–5 sentences expressing your current view, exactly as you'd write it to a peer."),
    ("Op-ed pitch",
     "If you were writing an op-ed this week, what's your topic and opening line?"),
]

STEPS = ["Welcome", "About You", "Style Profile", "Calibration", "Writing Samples", "Review & Submit"]

# ── Session state ──────────────────────────────────────────────────────────────
defaults = {
    "step": 0, "page": "survey",
    "first_name": "", "last_name": "", "title": "",
    "department": "", "email": "", "years_experience": "",
    "style_answers": {},
    "calibration": {},
    "writing_samples": ["", "", ""],
    "submitted": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def progress_bar():
    total, current = len(STEPS), st.session_state.step
    cols = st.columns(total)
    for i, col in enumerate(cols):
        color = "#c4a050" if i <= current else "#2a2a2a"
        col.markdown(f'<div style="height:3px;background:{color};border-radius:2px;"></div>',
                     unsafe_allow_html=True)
    st.markdown(f'<p class="step-label" style="text-align:right;margin-top:6px;">'
                f'Step {current+1} of {total} · {STEPS[current]}</p>',
                unsafe_allow_html=True)

def header():
    st.markdown('<p class="step-label">Voice Intelligence Survey</p>', unsafe_allow_html=True)
    progress_bar()
    st.markdown("---")

# ── Survey steps ───────────────────────────────────────────────────────────────
def show_welcome():
    st.markdown("## Your voice. *Captured.*")
    st.markdown("""
This survey captures how you think and write — so we can generate op-eds and
articles that sound genuinely like **you**.

It has four short sections:
1. **Your details** — name, role, background
2. **Style questions** — how you naturally write
3. **Calibration** — pick examples that match your style
4. **Writing samples** — short pieces in your own words

*Takes about 10–12 minutes. The more honest you are, the better the output.*
    """)
    st.button("Let's begin →", on_click=next_step, type="primary")


def show_about():
    st.markdown("## About you")
    st.caption("Tell us who you are and your role.")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.first_name = st.text_input("First name *", value=st.session_state.first_name)
    with c2:
        st.session_state.last_name = st.text_input("Last name *", value=st.session_state.last_name)
    st.session_state.title = st.text_input("Job title *", value=st.session_state.title,
                                            placeholder="e.g. Head of Equities")
    st.session_state.department = st.text_input("Department / team *", value=st.session_state.department,
                                                  placeholder="e.g. Institutional Sales")
    c3, c4 = st.columns(2)
    with c3:
        st.session_state.email = st.text_input("Email (optional)", value=st.session_state.email,
                                                placeholder="you@example.com")
    with c4:
        opts = ["", "0–2 years", "3–5 years", "6–10 years", "11–20 years", "20+ years"]
        st.session_state.years_experience = st.selectbox(
            "Years in financial services", opts,
            index=opts.index(st.session_state.years_experience))
    st.markdown("")
    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back: st.button("← Back", on_click=prev_step)
    with c_next:
        required = [st.session_state.first_name, st.session_state.last_name,
                    st.session_state.title, st.session_state.department]
        if st.button("Continue →", type="primary", disabled=not all(required)):
            next_step()


def show_style():
    st.markdown("## Your writing style")
    st.caption("Answer instinctively — first reaction is usually most accurate.")
    answers = st.session_state.style_answers
    for q in STYLE_QUESTIONS:
        st.markdown(f"**{q['question']}**")
        if q["type"] == "scale":
            c1, c2, c3 = st.columns([2, 3, 2])
            with c1: st.caption(q["left"])
            with c3: st.caption(q["right"])
            answers[q["id"]] = st.slider(
                q["question"], label_visibility="collapsed",
                min_value=1, max_value=5, value=answers.get(q["id"], 3),
                key=f"sl_{q['id']}")
        elif q["type"] == "radio":
            opts = q["options"]
            answers[q["id"]] = st.radio(
                q["question"], label_visibility="collapsed",
                options=opts,
                index=opts.index(answers[q["id"]]) if q["id"] in answers else 0,
                key=f"rd_{q['id']}")
        elif q["type"] == "multiselect":
            answers[q["id"]] = st.multiselect(
                q["question"], label_visibility="collapsed",
                options=q["options"], default=answers.get(q["id"], []),
                key=f"ms_{q['id']}")
        st.markdown("")
    st.session_state.style_answers = answers
    all_answered = all(answers.get(q["id"]) not in [None, "", []] for q in STYLE_QUESTIONS)
    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back: st.button("← Back", on_click=prev_step)
    with c_next:
        if st.button("Continue →", type="primary", disabled=not all_answered):
            next_step()


def show_calibration():
    st.markdown("## Calibration")
    st.markdown(
        "For each set below, read the three examples and pick the one that sounds "
        "**most like how you naturally write**. Don't pick the one you admire most — "
        "pick the one that's closest to *you*."
    )
    st.markdown("")
    cal = st.session_state.calibration

    for key, section in CALIBRATION.items():
        st.markdown(f"### {section['label']}")
        st.caption(section["question"])
        for opt in section["options"]:
            selected = cal.get(f"{key}_example") == opt["id"]
            border = "2px solid #c4a050" if selected else "1.5px solid #ddd"
            bg = "rgba(196,160,80,0.07)" if selected else "#fafafa"
            st.markdown(
                f'<div style="border:{border};background:{bg};border-radius:10px;'
                f'padding:1rem 1.2rem;margin-bottom:0.6rem;">'
                f'<strong style="color:#c4a050;">{opt["label"]}</strong><br/>'
                f'<span style="font-size:0.95em;color:#333;line-height:1.6;">{opt["text"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(f"✓ This one — {section['label']} {opt['label']}",
                         key=f"cal_{key}_{opt['id']}"):
                cal[f"{key}_example"] = opt["id"]
                st.session_state.calibration = cal
                st.rerun()
        if cal.get(f"{key}_example"):
            chosen = next(o for o in section["options"] if o["id"] == cal[f"{key}_example"])
            st.success(f"Selected: {chosen['label']}")
        st.markdown("")

    all_calibrated = all(f"{k}_example" in cal for k in CALIBRATION)
    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back: st.button("← Back", on_click=prev_step)
    with c_next:
        if st.button("Continue →", type="primary", disabled=not all_calibrated):
            next_step()


def show_writing():
    st.markdown("## Writing samples")
    st.markdown(
        "This is the most important section. **Write naturally** — don't edit yourself "
        "or try to sound impressive. We want your real voice, not your best voice."
    )
    samples = st.session_state.writing_samples
    for i, (label, prompt) in enumerate(WRITING_PROMPTS):
        st.markdown(f"**{i+1}. {label}**")
        st.caption(prompt)
        samples[i] = st.text_area(
            label, label_visibility="collapsed",
            value=samples[i],
            height=200 if i == 0 else 130,
            placeholder="Write freely..." if i > 0 else "Paste any writing here...",
            key=f"ws_{i}")
        if samples[i]:
            wc = len(samples[i].split())
            color = "#c4a050" if wc >= 50 else "#888"
            st.markdown(f'<p style="font-size:0.8em;color:{color};">{wc} words'
                        f'{"" if wc >= 50 else " — more detail improves accuracy"}</p>',
                        unsafe_allow_html=True)
        st.markdown("")
    st.session_state.writing_samples = samples
    has_sample = any(s.strip() for s in samples)
    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back: st.button("← Back", on_click=prev_step)
    with c_next:
        if st.button("Review →", type="primary", disabled=not has_sample):
            next_step()


def show_review():
    st.markdown("## Review & submit")
    st.caption("Check your details before we save your profile.")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.first_name} {st.session_state.last_name}**")
    st.markdown(f"{st.session_state.title} · {st.session_state.department}")
    if st.session_state.years_experience:
        st.caption(f"{st.session_state.years_experience} in financial services")
    st.markdown('</div>', unsafe_allow_html=True)

    answered = sum(1 for q in STYLE_QUESTIONS
                   if st.session_state.style_answers.get(q["id"]) not in [None, "", []])
    cal_done = sum(1 for k in CALIBRATION if f"{k}_example" in st.session_state.calibration)
    samples = st.session_state.writing_samples
    filled = sum(1 for s in samples if s.strip())
    total_words = sum(len(s.split()) for s in samples if s.strip())

    st.markdown(f"**Style questions:** {answered}/{len(STYLE_QUESTIONS)} answered")
    st.markdown(f"**Calibration:** {cal_done}/{len(CALIBRATION)} sections completed")
    st.markdown(f"**Writing samples:** {filled}/3 provided · {total_words} words")

    st.markdown("")
    c_back, c_submit, _ = st.columns([1, 1.5, 3])
    with c_back: st.button("← Edit", on_click=prev_step)
    with c_submit:
        if st.button("✦ Submit profile", type="primary"):
            with st.spinner("Analysing your writing and saving your profile..."):
                try:
                    nlp = analyse_text(st.session_state.writing_samples)
                    payload = {
                        "first_name":      st.session_state.first_name,
                        "last_name":       st.session_state.last_name,
                        "title":           st.session_state.title,
                        "department":      st.session_state.department,
                        "email":           st.session_state.email,
                        "years_experience": st.session_state.years_experience,
                        "style_answers":   st.session_state.style_answers,
                        "calibration":     st.session_state.calibration,
                        "writing_samples": st.session_state.writing_samples,
                        "nlp_metrics":     nlp,
                    }
                    payload["ai_prompt"] = build_prompt(payload, nlp)
                    save_response(payload)
                    st.session_state.submitted = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Something went wrong: {e}")


def show_success():
    st.markdown('<p class="step-label">Voice Intelligence Survey</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## ✦ Profile saved.")
    st.success(
        f"Thank you, {st.session_state.first_name}. Your writing style profile has been "
        "captured and will be used to generate content that authentically reflects your voice."
    )
    if st.button("Submit another profile"):
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()

# ── Admin ──────────────────────────────────────────────────────────────────────
def page_admin():
    st.markdown('<p class="step-label">Voice Intelligence · Admin</p>', unsafe_allow_html=True)
    st.markdown("## SME Profiles")
    st.markdown("---")

    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

    if not st.session_state.admin_authed:
        pwd = st.text_input("Admin password", type="password")
        if st.button("Unlock"):
            if pwd == st.secrets.get("admin_password", "changeme"):
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return

    with st.spinner("Loading profiles..."):
        try:
            df = load_all_responses()
        except Exception as e:
            st.error(f"Could not load: {e}")
            return

    if df.empty:
        st.info("No profiles submitted yet.")
        return

    st.markdown(f"**{len(df)} profile{'s' if len(df)!=1 else ''} submitted**")
    summary_cols = ["Timestamp","First Name","Last Name","Title","Department","Years Experience"]
    st.dataframe(df[[c for c in summary_cols if c in df.columns]],
                 use_container_width=True, hide_index=True)

    st.markdown("### Full profiles")
    for _, row in df.iterrows():
        name = f"{row.get('First Name','')} {row.get('Last Name','')}".strip()
        with st.expander(f"**{name}** — {row.get('Title','')} · {row.get('Department','')}"):
            st.caption(f"Submitted: {row.get('Timestamp','')}")

            # NLP metrics
            nlp_raw = row.get("NLP Metrics", "")
            if nlp_raw:
                try:
                    nlp = json.loads(nlp_raw)
                    st.markdown("**📊 Objective style metrics**")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Avg sentence length", f"{nlp.get('avg_sentence_length','–')} words")
                    m2.metric("Lexical diversity", nlp.get('lexical_diversity','–'))
                    m3.metric("Readability", nlp.get('readability_level','–'))
                    m4, m5, m6 = st.columns(3)
                    m4.metric("First person %", f"{nlp.get('first_person_pct','–')}%")
                    m5.metric("Passive voice", f"{nlp.get('passive_voice_per_sentence','–')}/sent")
                    m6.metric("Em-dashes", nlp.get('em_dashes','–'))
                    if nlp.get("distinctive_words"):
                        st.markdown(f"**Recurring vocabulary:** {', '.join(nlp['distinctive_words'][:10])}")
                except Exception:
                    pass

            # Calibration
            cal_raw = {k: row.get(k,"") for k in
                       ["Calibration Tone","Calibration Structure","Calibration Opening"]}
            if any(cal_raw.values()):
                st.markdown("**🎯 Calibration choices**")
                for k, v in cal_raw.items():
                    if v: st.markdown(f"- {k}: **{v}**")

            # Style answers
            st.markdown("**✏️ Style answers**")
            for q in STYLE_QUESTIONS:
                label = q["id"].replace("_"," ").title()
                val = row.get(label,"")
                if val:
                    if q["type"] == "scale":
                        st.markdown(f"- *{q['question']}*: **{val}/5** ({q['left']} ← → {q['right']})")
                    else:
                        st.markdown(f"- *{q['question']}*: {val}")

            # Writing samples
            st.markdown("**📝 Writing samples**")
            for i, (label, _) in enumerate(WRITING_PROMPTS):
                text = row.get(f"Writing Sample {i+1}","")
                if text:
                    st.markdown(f"*{label}*")
                    st.markdown(
                        f'<div class="section-card" style="font-size:0.9em;">{text}</div>',
                        unsafe_allow_html=True)

            # Generated prompt
            prompt = row.get("AI Prompt","")
            if prompt:
                st.markdown("**🤖 Generated AI Prompt**")
                st.text_area("Copy this prompt →", value=prompt, height=300,
                             key=f"prompt_{row.get('id','')}")

    st.markdown("---")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download all responses as CSV", csv,
                       "sme_voice_profiles.csv", "text/csv")
    if st.button("← Back to survey"):
        st.session_state.page = "survey"
        st.session_state.admin_authed = False
        st.rerun()

# ── Survey router ──────────────────────────────────────────────────────────────
def page_survey():
    if st.session_state.submitted:
        show_success(); return
    header()
    step = st.session_state.step
    if   step == 0: show_welcome()
    elif step == 1: show_about()
    elif step == 2: show_style()
    elif step == 3: show_calibration()
    elif step == 4: show_writing()
    elif step == 5: show_review()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✦ Voice Intelligence")
    st.markdown("SME Writing Style Survey")
    st.markdown("---")
    if st.button("📝 Take survey"):
        st.session_state.page = "survey"; st.rerun()
    if st.button("🔐 Admin — view profiles"):
        st.session_state.page = "admin"; st.rerun()

# ── Main router ────────────────────────────────────────────────────────────────
if st.session_state.page == "admin":
    page_admin()
else:
    page_survey()
