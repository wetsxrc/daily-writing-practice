import datetime as dt
import hashlib
import json
import os
import smtplib
import time
from email.header import Header
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

from topics import TOPICS

st.set_page_config(page_title="Daily Letter", page_icon="✍️", layout="centered")

# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
TZ = ZoneInfo("America/Toronto")
START_DATE = dt.date(2026, 10, 1)  # 不要修改！改了就等于从第一题重新开始
MAX_WORDS = 200
MAX_SWAPS = 3  # how many times a child may ask for a different topic per day
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]  # tried in order
LOCAL_FILE = "writing_history.json"  # fallback only (lost on redeploy!)
HEADERS = [
    "timestamp", "email", "name", "date", "topic_idx", "topic", "essay",
    "word_count", "score", "grammar", "vocabulary", "ideas", "clarity",
    "feedback_json",
]
CAT_LABEL = {
    "school": "📚 Learning",
    "life": "🏡 Daily life",
    "hobby": "🎨 Hobbies",
    "think": "💭 Big ideas",
}

# ---------------------------------------------------------------
# Optional family passcode (set APP_PASSCODE in secrets to turn on)
# ---------------------------------------------------------------
passcode = st.secrets.get("APP_PASSCODE", "")
if passcode and not st.session_state.get("unlocked"):
    entered = st.text_input("Family passcode", type="password")
    if entered == passcode:
        st.session_state["unlocked"] = True
        st.rerun()
    if entered:
        st.error("Wrong passcode.")
    st.stop()


# ---------------------------------------------------------------
# Storage: Google Sheets if configured, otherwise a local JSON file
# ---------------------------------------------------------------
@st.cache_resource
def get_sheet():
    if "gcp_service_account" not in st.secrets or "SHEET_ID" not in st.secrets:
        return None
    import gspread

    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    ws = gc.open_by_key(st.secrets["SHEET_ID"]).sheet1
    if not ws.row_values(1):
        ws.append_row(HEADERS)
    return ws


def _read_local():
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_entry(row):
    """Returns (ok, where_or_error)."""
    try:
        ws = get_sheet()
        if ws is not None:
            ws.append_row([row.get(h, "") for h in HEADERS], value_input_option="RAW")
            return True, "sheet"
        data = _read_local()
        data.append(row)
        with open(LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True, "local"
    except Exception as e:
        return False, str(e)


def load_entries(email):
    try:
        ws = get_sheet()
        rows = ws.get_all_records() if ws is not None else _read_local()
    except Exception as e:
        st.warning(f"Couldn't load your past letters: {e}")
        return []
    mine = [r for r in rows if str(r.get("email", "")).strip().lower() == email]
    return sorted(mine, key=lambda r: str(r.get("timestamp", "")))


# ---------------------------------------------------------------
# Daily topic: depends only on the calendar date + the person's email,
# so redeploying / restarting never resets it.
# ---------------------------------------------------------------
def today_local():
    return dt.datetime.now(TZ).date()


def topic_index(email, day, shift=0):
    offset = int(hashlib.sha256(email.encode("utf-8")).hexdigest(), 16) % len(TOPICS)
    return ((day - START_DATE).days + offset + shift * 37) % len(TOPICS)


# ---------------------------------------------------------------
# AI grading (returns structured JSON, score is computed by us)
# ---------------------------------------------------------------
SYSTEM = """You are a warm, encouraging English writing teacher for a Grade 5 student in Canada. The student is an English learner (ESL) who arrived two years ago, so judge the writing at that level, not against a native speaker.

Return ONE JSON object with exactly these keys:
{
  "rubric": {"grammar": <int 0-25>, "vocabulary": <int 0-25>, "ideas": <int 0-25>, "clarity": <int 0-25>},
  "grade_label": "<2-4 warm words, e.g. Nice work!>",
  "strengths": ["<2-3 short, specific things done well>"],
  "corrections": [{"original": "<exact words from the student>", "suggestion": "<corrected words>", "why": "<one short, gentle reason>"}],
  "tip": "<ONE concrete thing to try in tomorrow's writing>",
  "encouragement": "<one warm sentence to the student>",
  "parent_note_zh": "<2 short sentences in Chinese for the parent: the main strength and the main thing to practice>"
}

Rules:
- Rubric values are integers. Guide for each: 15-18 = simple but understandable; 19-22 = good with few errors; 23-25 = excellent for Grade 5. Be generous but honest.
- corrections: at most 5, only real errors that matter (grammar, spelling, word choice). If there are none, use an empty list.
- Do NOT rewrite the whole text and do NOT write a model answer.
- Every English string must be simple enough for a Grade 5 ESL reader.
- Never be harsh or sarcastic. Focus on progress."""


def parse_feedback(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:]
    data = json.loads(t)
    raw = data.get("rubric", {})
    rub = {k: max(0, min(25, int(raw.get(k, 0)))) for k in ("grammar", "vocabulary", "ideas", "clarity")}
    data["rubric"] = rub
    data["score"] = sum(rub.values())
    data["strengths"] = list(data.get("strengths") or [])
    data["corrections"] = list(data.get("corrections") or [])
    return data


def grade(topic, essay, name, words):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        response_mime_type="application/json",
        temperature=0.4,
        max_output_tokens=1500,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    prompt = f"Student first name: {name}\nTopic: {topic}\nWord count: {words}\n\nStudent's writing:\n{essay}"
    last_err = None
    for model in MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
                return parse_feedback(resp.text)
            except Exception as e:
                last_err = e
                msg = str(e)
                retryable = (
                    "503" in msg or "UNAVAILABLE" in msg
                    or isinstance(e, (json.JSONDecodeError, ValueError, KeyError))
                )
                if retryable and attempt == 0:
                    time.sleep(3)
                    continue
                break  # quota (429), model not found, etc. -> try the next model
    raise last_err


# ---------------------------------------------------------------
# Email to parent
# ---------------------------------------------------------------
def send_email(name, email, topic, essay, fb):
    sender = st.secrets.get("EMAIL_SENDER", "")
    password = st.secrets.get("EMAIL_PASSWORD", "")
    receiver = st.secrets.get("EMAIL_RECEIVER", "")
    if not (sender and password and receiver):
        return False, "Email settings are missing in secrets."

    r = fb["rubric"]
    fixes = "\n".join(
        f'- "{c.get("original", "")}" -> "{c.get("suggestion", "")}" ({c.get("why", "")})'
        for c in fb["corrections"]
    ) or "- None. Great!"
    body = f"""{name} ({email}) just finished today's letter.

Topic: {topic}

Score: {fb['score']}/100
Grammar {r['grammar']}/25 | Vocabulary {r['vocabulary']}/25 | Ideas {r['ideas']}/25 | Clarity {r['clarity']}/25

家长小结: {fb.get('parent_note_zh', '')}

--- {name}'s writing ---
{essay}

--- Corrections ---
{fixes}

Tip for tomorrow: {fb.get('tip', '')}
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(f"Daily Letter: {name} scored {fb['score']}/100", "utf-8")
    msg["From"] = sender
    msg["To"] = receiver
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(sender, password)
            s.send_message(msg)
        return True, "sent"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------
def render_feedback(fb):
    c1, c2 = st.columns([1, 2])
    c1.metric("Score", f"{fb['score']} / 100")
    c2.subheader(fb.get("grade_label", "Nice work!"))
    for label, key in (("Grammar", "grammar"), ("Vocabulary", "vocabulary"), ("Ideas", "ideas"), ("Clarity", "clarity")):
        v = fb["rubric"][key]
        st.progress(v / 25, text=f"{label}: {v}/25")
    if fb.get("strengths"):
        st.markdown("**🌟 What went well**")
        for s in fb["strengths"]:
            st.markdown(f"- {s}")
    if fb.get("corrections"):
        st.markdown("**✏️ Let's polish**")
        for c in fb["corrections"]:
            st.markdown(f"~~{c.get('original', '')}~~ → **{c.get('suggestion', '')}**")
            st.caption(c.get("why", ""))
    if fb.get("tip"):
        st.info(f"💡 Try tomorrow: {fb['tip']}")
    if fb.get("encouragement"):
        st.success(fb["encouragement"])


def bump_swap(key):
    st.session_state[key] = st.session_state.get(key, 0) + 1


# ---------------------------------------------------------------
# Who is writing? (name + email, remembered through the page URL)
# ---------------------------------------------------------------
st.sidebar.title("✍️ Daily Letter")
qp = st.query_params
name = st.sidebar.text_input("Name", value=qp.get("name", ""), key="name_in").strip()
email = st.sidebar.text_input("Email", value=qp.get("email", ""), key="email_in").strip().lower()
valid_email = "@" in email and "." in email.split("@")[-1]

if name and valid_email:
    if qp.get("name") != name or qp.get("email") != email:
        st.query_params["name"] = name
        st.query_params["email"] = email
    st.sidebar.caption("Tip: bookmark this page. Next time you won't need to type again.")

page = st.sidebar.radio("Go to", ["✍️ Write", "📈 My progress"])

if not (name and valid_email):
    st.title("✍️ Daily Letter")
    st.info("Type your name and email in the left sidebar to start. (On a phone, tap the arrow at the top left.)")
    st.stop()

day = today_local()

# ---------------------------------------------------------------
# PAGE: Write
# ---------------------------------------------------------------
if page == "✍️ Write":
    st.title(f"Hi {name}! ✍️")

    swap_key = f"swaps:{email}:{day}"
    swaps = st.session_state.get(swap_key, 0)
    idx = topic_index(email, day, swaps)
    cat, topic = TOPICS[idx]

    st.caption(f"{CAT_LABEL[cat]}  ·  {day:%A, %B %d}")
    st.info(f"### {topic}")
    if swaps < MAX_SWAPS:
        st.button("🔄 Give me a different topic", on_click=bump_swap, args=(swap_key,))

    essay = st.text_area(
        f"Write your letter here ({MAX_WORDS} words or fewer):",
        height=260,
        key=f"draft:{email}:{day}:{swaps}",
        placeholder="Start typing here...",
    )
    words = len(essay.split())
    st.caption(f"📝 {words} / {MAX_WORDS} words  (the number updates when you click outside the box)")
    if words > MAX_WORDS:
        st.error(f"Too long by {words - MAX_WORDS} words. Try to make it shorter. Short and clear is great!")

    if st.button("🚀 Submit", type="primary", use_container_width=True):
        if words == 0:
            st.warning("Please write something first.")
        elif words > MAX_WORDS:
            st.error(f"Please keep it to {MAX_WORDS} words or fewer, then submit again.")
        else:
            fb = None
            with st.spinner("Your teacher is reading your letter..."):
                try:
                    fb = grade(topic, essay, name, words)
                except Exception as e:
                    st.error("The teacher is busy right now. Your writing is still here. Please wait one minute and press Submit again.")
                    with st.expander("Details for parent"):
                        st.code(str(e))
            if fb:
                now = dt.datetime.now(TZ)
                row = {
                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "email": email, "name": name, "date": day.isoformat(),
                    "topic_idx": idx, "topic": topic, "essay": essay,
                    "word_count": words, "score": fb["score"],
                    "grammar": fb["rubric"]["grammar"],
                    "vocabulary": fb["rubric"]["vocabulary"],
                    "ideas": fb["rubric"]["ideas"],
                    "clarity": fb["rubric"]["clarity"],
                    "feedback_json": json.dumps(fb, ensure_ascii=False),
                }
                saved = save_entry(row)
                mailed = send_email(name, email, topic, essay, fb)
                st.session_state["result"] = {
                    "who": (email, str(day)), "fb": fb, "saved": saved, "mailed": mailed,
                }

    res = st.session_state.get("result")
    if res and res["who"] == (email, str(day)):
        st.markdown("---")
        st.subheader("📝 Your teacher's feedback")
        render_feedback(res["fb"])
        if not res["saved"][0]:
            st.warning("Your letter could not be saved to your progress history.")
            st.caption(res["saved"][1])
        if not res["mailed"][0]:
            st.warning("The email to your parent could not be sent.")
            st.caption(res["mailed"][1])

# ---------------------------------------------------------------
# PAGE: My progress
# ---------------------------------------------------------------
else:
    st.title("📈 My progress")
    entries = load_entries(email)
    if not entries:
        st.info("No letters yet. Write your first one today!")
        st.stop()

    df = pd.DataFrame(entries)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    dates = {str(r.get("date")) for r in entries}
    d = day
    if d.isoformat() not in dates:
        d -= dt.timedelta(days=1)
    streak = 0
    while d.isoformat() in dates:
        streak += 1
        d -= dt.timedelta(days=1)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Letters", len(entries))
    m2.metric("Avg (last 7)", f"{df['score'].tail(7).mean():.0f}")
    m3.metric("Best", f"{df['score'].max():.0f}")
    m4.metric("Streak 🔥", f"{streak} days")

    st.line_chart(df.set_index("timestamp")["score"], height=220)

    st.subheader("Past letters")
    for r in reversed(entries[-30:]):
        with st.expander(f"{r.get('date')}  ·  {r.get('score')}/100  ·  {str(r.get('topic', ''))[:60]}"):
            st.markdown(f"**{r.get('topic', '')}**")
            st.write(r.get("essay", ""))
            try:
                render_feedback(json.loads(r["feedback_json"]))
            except Exception:
                st.caption("(No feedback saved for this letter.)")
