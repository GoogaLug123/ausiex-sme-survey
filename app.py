import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AUSIEX · SME Voice Survey",
    page_icon="✦",
    layout="centered",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Lora:ital,wght@0,400;0,500;1,400&display=swap');

html, body, [class*="css"] {
    font-family: 'Lora', Georgia, serif;
}
h1, h2, h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
}
.step-label {
    font-family: 'Playfair Display', serif;
    font-size: 0.7em;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #c4a050;
}
.section-card {
    background: rgba(196,160,80,0.06);
    border: 1px solid rgba(196,160,80,0.25);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ── Airtable connection ────────────────────────────────────────────────────────
AIRTABLE_TOKEN  = st.secrets["airtable"]["token"]
AIRTABLE_BASE   = st.secrets["airtable"]["base_id"]
AIRTABLE_TABLE  = st.secrets["airtable"]["table_name"]   # e.g. "Responses"
AIRTABLE_URL    = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}"
HEADERS         = {"Authorization": f"Bearer {AIRTABLE_TOKEN}",
                   "Content-Type": "application/json"}

def save_response(data: dict):
    """Save one survey response as an Airtable record."""
    style = data["style_answers"]
    fields = {
        "Timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "First Name":       data.get("first_name", ""),
        "Last Name":        data.get("last_name", ""),
        "Title":            data.get("title", ""),
        "Department":       data.get("department", ""),
        "Email":            data.get("email", ""),
        "Years Experience": data.get("years_experience", ""),
        # Scale answers (stored as numbers)
        "Tone":             style.get("tone", ""),
        "Complexity":       style.get("complexity", ""),
        "Sentence Length":  style.get("sentence_length", ""),
        "Jargon":           style.get("jargon", ""),
        "Contrarian":       style.get("contrarian", ""),
        # Choice answers (stored as text)
        "Structure":        style.get("structure", ""),
        "Perspective":      style.get("perspective", ""),
        "Hooks":            style.get("hooks", ""),
        "Closing":          style.get("closing", ""),
        "Evidence":         ", ".join(style.get("evidence", [])),
        # Writing samples
        "Writing Sample 1": data["writing_samples"][0],
        "Writing Sample 2": data["writing_samples"][1],
        "Writing Sample 3": data["writing_samples"][2],
    }
    # Remove empty strings so Airtable doesn't complain
    fields = {k: v for k, v in fields.items() if v != ""}
    resp = requests.post(AIRTABLE_URL, headers=HEADERS, json={"fields": fields})
    resp.raise_for_status()

def load_all_responses():
    """Load all records from Airtable and return as a DataFrame."""
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
    rows = [{"id": r["id"], **r["fields"]} for r in records]
    return pd.DataFrame(rows)

# ── Survey content ─────────────────────────────────────────────────────────────
STYLE_QUESTIONS = [
    {"id": "tone", "type": "scale",
     "question": "How would you describe your natural writing tone?",
     "left": "Formal & authoritative", "right": "Conversational & approachable"},
    {"id": "complexity", "type": "scale",
     "question": "How do you handle complex financial concepts?",
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
         "Institutional voice — 'AUSIEX believes…', 'The data shows…'",
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
         "Data and statistics",
         "Real-world case studies",
         "Historical analogies",
         "Expert citations",
         "Personal experience",
         "First principles reasoning",
     ]},
]

WRITING_PROMPTS = [
    ("Existing writing sample",
     "Paste a recent LinkedIn post, article excerpt, or internal brief you've written (any length)."),
    ("Live prompt",
     "Describe your view on a current market trend or industry issue — write 2–4 sentences as you naturally would."),
    ("Op-ed pitch",
     "If you were writing an op-ed today, what topic would you choose and what's your opening line?"),
]

STEPS = ["Welcome", "About You", "Style Profile", "Writing Samples", "Review & Submit"]

# ── Session state init ─────────────────────────────────────────────────────────
defaults = {
    "step": 0,
    "page": "survey",
    "first_name": "", "last_name": "", "title": "",
    "department": "", "email": "", "years_experience": "",
    "style_answers": {},
    "writing_samples": ["", "", ""],
    "submitted": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helpers ────────────────────────────────────────────────────────────────────
def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

def progress_bar():
    total = len(STEPS)
    current = st.session_state.step
    cols = st.columns(total)
    for i, col in enumerate(cols):
        color = "#c4a050" if i <= current else "#2a2a2a"
        col.markdown(
            f'<div style="height:3px;background:{color};border-radius:2px;"></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<p class="step-label" style="text-align:right;margin-top:6px;">'
        f'Step {current + 1} of {total} · {STEPS[current]}</p>',
        unsafe_allow_html=True,
    )

def header():
    st.markdown('<p class="step-label">AUSIEX · Voice Intelligence</p>', unsafe_allow_html=True)
    progress_bar()
    st.markdown("---")

# ── Survey pages ───────────────────────────────────────────────────────────────
def show_welcome():
    st.markdown("## Your voice. *Captured.*")
    st.markdown("""
This survey helps us understand how you think and write — so we can generate op-eds,
articles, and commentary that sound genuinely like **you**.

It has three short sections:
1. **Your details** — name, role, background
2. **10 style questions** — how you naturally write and communicate
3. **3 writing prompts** — short samples that show your voice in action

There are no right answers. The more honest you are, the more authentic the generated content will be.

*Takes about 8–10 minutes.*
    """)
    st.button("Let's begin →", on_click=next_step, type="primary")


def show_about():
    st.markdown("## About you")
    st.caption("Tell us who you are and your role at AUSIEX.")

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
                                                placeholder="you@ausiex.com.au")
    with c4:
        options = ["", "0–2 years", "3–5 years", "6–10 years", "11–20 years", "20+ years"]
        st.session_state.years_experience = st.selectbox(
            "Years in financial services",
            options,
            index=options.index(st.session_state.years_experience),
        )

    st.markdown("")
    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back:
        st.button("← Back", on_click=prev_step)
    with c_next:
        required = [st.session_state.first_name, st.session_state.last_name,
                    st.session_state.title, st.session_state.department]
        if st.button("Continue →", type="primary", disabled=not all(required)):
            next_step()


def show_style():
    st.markdown("## Your writing style")
    st.caption("Answer instinctively — there's no wrong answer.")

    answers = st.session_state.style_answers

    for q in STYLE_QUESTIONS:
        st.markdown(f"**{q['question']}**")

        if q["type"] == "scale":
            c1, c2, c3 = st.columns([2, 3, 2])
            with c1: st.caption(q["left"])
            with c3: st.caption(q["right"])
            answers[q["id"]] = st.slider(
                label=q["question"], label_visibility="collapsed",
                min_value=1, max_value=5,
                value=answers.get(q["id"], 3),
                key=f"sl_{q['id']}",
            )

        elif q["type"] == "radio":
            opts = q["options"]
            current_idx = opts.index(answers[q["id"]]) if q["id"] in answers else 0
            answers[q["id"]] = st.radio(
                label=q["question"], label_visibility="collapsed",
                options=opts, index=current_idx,
                key=f"rd_{q['id']}",
            )

        elif q["type"] == "multiselect":
            answers[q["id"]] = st.multiselect(
                label=q["question"], label_visibility="collapsed",
                options=q["options"],
                default=answers.get(q["id"], []),
                key=f"ms_{q['id']}",
            )

        st.markdown("")

    st.session_state.style_answers = answers

    all_answered = all(
        answers.get(q["id"]) not in [None, "", []]
        for q in STYLE_QUESTIONS
    )

    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back:
        st.button("← Back", on_click=prev_step)
    with c_next:
        if st.button("Continue →", type="primary", disabled=not all_answered):
            next_step()


def show_writing():
    st.markdown("## Writing samples")
    st.markdown(
        "These samples are the most important part. **Don't edit yourself** — "
        "write as you naturally would. Answer at least one prompt."
    )

    samples = st.session_state.writing_samples

    for i, (label, prompt) in enumerate(WRITING_PROMPTS):
        st.markdown(f"**{i+1}. {label}**")
        st.caption(prompt)
        samples[i] = st.text_area(
            label=label, label_visibility="collapsed",
            value=samples[i],
            height=180 if i == 0 else 120,
            placeholder="Write freely..." if i > 0 else "Paste any writing here...",
            key=f"ws_{i}",
        )
        if samples[i]:
            st.caption(f"{len(samples[i].split())} words")
        st.markdown("")

    st.session_state.writing_samples = samples
    has_sample = any(s.strip() for s in samples)

    c_back, c_next, _ = st.columns([1, 1, 4])
    with c_back:
        st.button("← Back", on_click=prev_step)
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
    st.markdown(f"**Style questions:** {answered} of {len(STYLE_QUESTIONS)} answered")

    samples = st.session_state.writing_samples
    filled = sum(1 for s in samples if s.strip())
    total_words = sum(len(s.split()) for s in samples if s.strip())
    st.markdown(f"**Writing samples:** {filled} of 3 provided · {total_words} words total")

    st.markdown("")
    c_back, c_submit, _ = st.columns([1, 1.5, 3])
    with c_back:
        st.button("← Edit", on_click=prev_step)
    with c_submit:
        if st.button("✦ Submit profile", type="primary"):
            with st.spinner("Saving your profile..."):
                try:
                    save_response({
                        "first_name":      st.session_state.first_name,
                        "last_name":       st.session_state.last_name,
                        "title":           st.session_state.title,
                        "department":      st.session_state.department,
                        "email":           st.session_state.email,
                        "years_experience": st.session_state.years_experience,
                        "style_answers":   st.session_state.style_answers,
                        "writing_samples": st.session_state.writing_samples,
                    })
                    st.session_state.submitted = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Something went wrong saving your response: {e}")


def show_success():
    st.markdown('<p class="step-label">AUSIEX · Voice Intelligence</p>', unsafe_allow_html=True)
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


# ── Admin page ─────────────────────────────────────────────────────────────────
def page_admin():
    st.markdown('<p class="step-label">AUSIEX · Voice Intelligence · Admin</p>', unsafe_allow_html=True)
    st.markdown("## SME Profiles")
    st.markdown("---")

    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

    if not st.session_state.admin_authed:
        pwd = st.text_input("Admin password", type="password")
        if st.button("Unlock"):
            if pwd == st.secrets.get("admin_password", "ausiex2024"):
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return

    with st.spinner("Loading profiles from Airtable..."):
        try:
            df = load_all_responses()
        except Exception as e:
            st.error(f"Could not load responses: {e}")
            return

    if df.empty:
        st.info("No profiles submitted yet.")
        return

    st.markdown(f"**{len(df)} profile{'s' if len(df) != 1 else ''} submitted**")
    st.markdown("")

    # Summary table
    summary_cols = ["Timestamp", "First Name", "Last Name", "Title", "Department", "Years Experience"]
    available = [c for c in summary_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)

    # Individual profile expanders
    st.markdown("### Full profiles")
    for _, row in df.iterrows():
        name = f"{row.get('First Name','')} {row.get('Last Name','')}".strip()
        with st.expander(f"**{name}** — {row.get('Title','')} · {row.get('Department','')}"):
            st.caption(f"Submitted: {row.get('Timestamp','')}")

            st.markdown("**Style answers**")
            scale_qs = [q for q in STYLE_QUESTIONS if q["type"] == "scale"]
            for q in scale_qs:
                label = q["id"].replace("_", " ").title()
                val = row.get(label, "")
                if val:
                    st.markdown(f"- *{q['question']}*: **{val}/5**  ({q['left']} ← → {q['right']})")

            other_qs = [q for q in STYLE_QUESTIONS if q["type"] != "scale"]
            for q in other_qs:
                label = q["id"].replace("_", " ").title()
                val = row.get(label, "")
                if val:
                    st.markdown(f"- *{q['question']}*: {val}")

            st.markdown("**Writing samples**")
            for i, (label, _) in enumerate(WRITING_PROMPTS):
                text = row.get(f"Writing Sample {i+1}", "")
                if text:
                    st.markdown(f"*{label}*")
                    st.markdown(
                        f'<div class="section-card" style="font-size:0.9em;">{text}</div>',
                        unsafe_allow_html=True,
                    )

    st.markdown("---")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download all responses as CSV", csv,
                       "ausiex_sme_profiles.csv", "text/csv")

    if st.button("← Back to survey"):
        st.session_state.page = "survey"
        st.session_state.admin_authed = False
        st.rerun()


# ── Survey router ──────────────────────────────────────────────────────────────
def page_survey():
    if st.session_state.submitted:
        show_success()
        return
    header()
    step = st.session_state.step
    if step == 0:   show_welcome()
    elif step == 1: show_about()
    elif step == 2: show_style()
    elif step == 3: show_writing()
    elif step == 4: show_review()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✦ AUSIEX")
    st.markdown("Voice Intelligence")
    st.markdown("---")
    if st.button("📝 Take survey"):
        st.session_state.page = "survey"
        st.rerun()
    if st.button("🔐 Admin — view profiles"):
        st.session_state.page = "admin"
        st.rerun()

# ── Main router ────────────────────────────────────────────────────────────────
if st.session_state.page == "admin":
    page_admin()
else:
    page_survey()
