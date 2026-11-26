import datetime
import json
import os
import random
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai
import gspread
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Grade 5 Daily Writing & Portfolio",
    page_icon="✍️",
    layout="centered",
)

api_key = st.secrets.get("GEMINI_API_KEY", "")
HISTORY_FILE = "writing_history.json"
TOPICS_FILE = "topic_bank.json"

# ---------------------------------------------------------
# Initial 35 Grade 5 Topics
# ---------------------------------------------------------
INITIAL_TOPIC_BANK = [
    "Imagine you are building a time machine. Which period in history would you visit first and why?",
    "If you could create one new rule for recess at your school, what would it be and how would it help?",
    "Describe your favorite afternoon snack using sensory words (sight, smell, taste, texture).",
    "If your pet or a favorite animal could talk for 10 minutes, what questions would you ask it?",
    "What was the most interesting or surprising thing that happened at school this week?",
    "Imagine you found a mysterious small brass key in your bedroom. What hidden box or secret door does it open?",
    "What is your favorite outdoor game or sport to play with friends, and what makes it exciting?",
    "If you could travel anywhere in Canada tomorrow, where would you go and what would you explore?",
    "If you could design a brand-new video game or board game, what would the main goal and rules be?",
    "If you woke up tomorrow with the ability to turn invisible for one day, what would you do?",
    "Write about a time you tried something completely new. How did you feel before and after?",
    "If you could trade places with any character in a book or movie for a day, who would it be?",
    "What is the best piece of advice a family member or teacher has ever given you?",
    "If you had $100 to spend on making your neighborhood or school a better place, how would you use it?",
    "Describe what your dream bedroom would look like if you could design every detail.",
    "Imagine you are an astronaut landing on a newly discovered planet. What does the landscape look like?",
    "If you could invent a robot to help with one daily chore at home, how would it work?",
    "Write a story about a day when gravity suddenly stopped working at your school for one hour.",
    "What is your favorite season of the year in Canada, and what activities do you enjoy most during it?",
    "If you could open your own restaurant or bakery, what would be on the menu?",
    "Describe a memorable family road trip or weekend adventure you have been on.",
    "If you could have any superpower, would you choose flying, super speed, or reading minds? Explain why.",
    "Imagine you shrunk to the size of an ant for an afternoon. What would your backyard look like?",
    "What is one skill or hobby you would love to master this year, and how do you plan to practice?",
    "Write about a book you read recently that you would recommend to a friend.",
    "If you were principal of your school for one day, what special event would you organize?",
    "Describe the wildest weather storm you have ever seen from safely inside your house.",
    "If you could invite three famous people (from history or today) to dinner, who would you pick?",
    "What makes someone a truly good friend? Give examples from your own life.",
    "Imagine you found a stranded baby dragon in your garage. How would you take care of it secretly?",
    "If you could live inside any video game world for a weekend, which game would you choose?",
    "Write about a time you solved a difficult problem or puzzle. What steps did you take?",
    "What is your favorite holiday tradition with your family, and why is it special to you?",
    "If animals could run the world for a week, which animal would be the best leader?",
    "Describe a futuristic school in the year 2100. How would students learn and travel to class?",
]


# ---------------------------------------------------------
# Google Sheets Connection (History & Topic_Bank Tabs)
# ---------------------------------------------------------
def get_gsheet_spreadsheet():
    """Connect to the target Google Spreadsheet."""
    if "gcp_service_account" not in st.secrets:
        return None
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds_dict)

        sheet_id = st.secrets.get("SHEET_ID", "")
        sheet_url = st.secrets.get("SPREADSHEET_URL", "")
        sheet_name = st.secrets.get("SHEET_NAME", "Daily Writing History")

        if sheet_id:
            return gc.open_by_key(sheet_id)
        elif sheet_url:
            return gc.open_by_url(sheet_url)
        else:
            return gc.open(sheet_name)
    except Exception:
        return None


def get_gsheet_worksheet():
    sh = get_gsheet_spreadsheet()
    return sh.sheet1 if sh is not None else None


def get_topic_bank_worksheet():
    """Get or automatically create the 'Topic_Bank' tab in Google Sheets."""
    sh = get_gsheet_spreadsheet()
    if sh is None:
        return None
    try:
        try:
            ws = sh.worksheet("Topic_Bank")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="Topic_Bank", rows=1000, cols=2)
            ws.append_row(["created_at", "topic"])
        return ws
    except Exception:
        return None


# ---------------------------------------------------------
# Topic Bank Load, Save & Auto-Replenish (+35 when <= 5 left)
# ---------------------------------------------------------
def load_topic_bank(force_refresh=False):
    """Load the master topic list from Google Sheets (Topic_Bank) or local JSON."""
    if not force_refresh and "master_topic_bank" in st.session_state:
        return st.session_state.master_topic_bank

    topics = []
    ws = get_topic_bank_worksheet()
    if ws is not None:
        try:
            col_values = ws.col_values(2)  # Column B is 'topic'
            topics = [t.strip() for t in col_values[1:] if t.strip()]
            if not topics:
                # First-time initialization: seed the 35 initial topics into Google Sheets
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows = [[now_str, t] for t in INITIAL_TOPIC_BANK]
                ws.append_rows(rows)
                topics = list(INITIAL_TOPIC_BANK)
        except Exception:
            pass

    if not topics and os.path.exists(TOPICS_FILE):
        try:
            with open(TOPICS_FILE, "r", encoding="utf-8") as f:
                topics = json.load(f)
        except Exception:
            topics = []

    if not topics:
        topics = list(INITIAL_TOPIC_BANK)

    # Deduplicate while preserving order
    seen = set()
    unique_topics = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            unique_topics.append(t)

    st.session_state.master_topic_bank = unique_topics
    return unique_topics


def append_topics_to_storage(new_topics):
    """Save newly generated topics to Google Sheets (Topic_Bank) and local JSON."""
    if not new_topics:
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws = get_topic_bank_worksheet()
    if ws is not None:
        try:
            rows = [[now_str, t] for t in new_topics]
            ws.append_rows(rows)
        except Exception:
            pass

    current_bank = load_topic_bank(force_refresh=False)
    for t in new_topics:
        if t not in current_bank:
            current_bank.append(t)
    st.session_state.master_topic_bank = current_bank

    try:
        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(current_bank, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def generate_35_new_topics(existing_topics):
    """Call Gemini API to generate 35 fresh, non-duplicate Grade 5 writing prompts."""
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    recent_sample = "\n".join(f"- {t}" for t in existing_topics[-40:])

    prompt = f"""
    You are an inspiring Grade 5 English teacher in Canada.
    Generate exactly 35 brand-new, creative, age-appropriate daily English writing prompts for 10-11 year old students.

    Requirements:
    1. Mix diverse themes: imaginative storytelling, school life, Canadian seasons/nature, science & space, animals, problem-solving, humor, and personal reflection.
    2. Each prompt should be 1 to 2 clear, engaging sentences that encourage students to write 100-200 words.
    3. Do NOT repeat or closely copy any of these existing topics:
    {recent_sample}

    Output format:
    Return ONLY a numbered list from 1 to 35, one prompt per line, with no extra introduction or conclusion.
    """

    models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    raw_text = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw_text = response.text
            if raw_text:
                break
        except Exception:
            continue

    if not raw_text:
        try:
            available_flash = [
                m.name.replace("models/", "")
                for m in client.models.list()
                if "flash" in m.name.lower()
                and "lite" not in m.name.lower()
                and "image" not in m.name.lower()
                and "audio" not in m.name.lower()
            ]
            if available_flash:
                available_flash.sort(reverse=True)
                response = client.models.generate_content(
                    model=available_flash[0],
                    contents=prompt,
                )
                raw_text = response.text
        except Exception:
            return []

    if not raw_text:
        return []

    existing_set = {t.lower().strip() for t in existing_topics}
    parsed_topics = []

    for line in raw_text.splitlines():
        cleaned = re.sub(r"^\s*\d+[\.\)\-:]\s*", "", line).strip()
        cleaned = cleaned.strip('"').strip("'").strip()
        if len(cleaned) > 15 and cleaned.lower() not in existing_set:
            existing_set.add(cleaned.lower())
            parsed_topics.append(cleaned)

    return parsed_topics[:35]


# ---------------------------------------------------------
# Writing History Persistence
# ---------------------------------------------------------
def load_history(force_refresh=False):
    """Cache history in session_state so button clicks are instant."""
    if not force_refresh and "cached_history" in st.session_state:
        return st.session_state.cached_history

    records_list = []
    ws = get_gsheet_worksheet()
    if ws is not None:
        try:
            records = ws.get_all_records()
            if records:
                records_list = [
                    {
                        "timestamp": str(r.get("timestamp", "")),
                        "student_name": str(r.get("student_name", "")),
                        "email": str(r.get("email", "")).strip().lower(),
                        "topic": str(r.get("topic", "")),
                        "user_input": str(r.get("user_input", "")),
                        "ai_feedback": str(r.get("ai_feedback", "")),
                    }
                    for r in records
                ]
        except Exception:
            pass

    if not records_list and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                records_list = json.load(f)
        except Exception:
            records_list = []

    st.session_state.cached_history = records_list
    return records_list


def save_submission(student_name, email, topic, user_input, ai_feedback):
    """Save submission to both Google Sheets (cloud) and local JSON."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_email = email.strip().lower()

    ws = get_gsheet_worksheet()
    if ws is not None:
        try:
            ws.append_row([
                timestamp,
                student_name,
                clean_email,
                topic,
                user_input,
                ai_feedback,
            ])
        except Exception as e:
            st.warning(f"Cloud sync warning (saved locally): {e}")

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append({
        "student_name": student_name,
        "email": clean_email,
        "topic": topic,
        "user_input": user_input,
        "ai_feedback": ai_feedback,
        "timestamp": timestamp,
    })

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    load_history(force_refresh=True)


# ---------------------------------------------------------
# Topic Pool Management & Auto-Replenish Trigger
# ---------------------------------------------------------
if "skipped_topics" not in st.session_state:
    st.session_state.skipped_topics = set()


def get_available_topics(student_email="", auto_replenish=True):
    """Return uncompleted topics for this student; auto-generate 35 more when <= 5 remain."""
    master_bank = load_topic_bank()
    all_history = load_history()
    clean_email = student_email.strip().lower()

    if clean_email:
        completed_set = {
            item["topic"]
            for item in all_history
            if item.get("email", "").strip().lower() == clean_email
        }
    else:
        completed_set = set()

    # Uncompleted topics in the entire bank for this student
    uncompleted_topics = [t for t in master_bank if t not in completed_set]

    # Auto-replenish trigger: when uncompleted topics drop to <= 5, generate 35 new topics
    if auto_replenish and len(uncompleted_topics) <= 5:
        with st.spinner("✨ Only a few topics left! Creating 35 brand-new topics for you..."):
            newly_generated = generate_35_new_topics(master_bank)
            if newly_generated:
                append_topics_to_storage(newly_generated)
                master_bank = load_topic_bank()
                uncompleted_topics = [
                    t for t in master_bank if t not in completed_set
                ]

    available = [
        t
        for t in uncompleted_topics
        if t not in st.session_state.skipped_topics
    ]

    # If user skipped all remaining topics in this session, reset skipped list
    if not available:
        st.session_state.skipped_topics = set()
        available = list(uncompleted_topics)

    if not available:
        available = list(master_bank)

    return available


def pick_new_topic(exclude_topic=None, student_email="", auto_replenish=True):
    available = get_available_topics(
        student_email=student_email, auto_replenish=auto_replenish
    )
    candidates = [t for t in available if t != exclude_topic]
    if candidates:
        return random.choice(candidates)
    return random.choice(available)


if "topic" not in st.session_state:
    st.session_state.topic = pick_new_topic(auto_replenish=True)


def handle_new_topic():
    current = st.session_state.get("topic", "")
    email = st.session_state.get("student_email_input", "")
    st.session_state.topic = pick_new_topic(
        exclude_topic=current, student_email=email, auto_replenish=True
    )


def handle_skip_topic():
    current = st.session_state.get("topic", "")
    email = st.session_state.get("student_email_input", "")
    if current:
        st.session_state.skipped_topics.add(current)
    st.session_state.topic = pick_new_topic(
        exclude_topic=current, student_email=email, auto_replenish=True
    )


# ---------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------
st.sidebar.title("📖 Navigation")
page = st.sidebar.radio(
    "Go to:", ["✍️ Daily Practice", "📚 Writing History"], index=0
)

# ---------------------------------------------------------
# PAGE 1: Daily Practice
# ---------------------------------------------------------
if page == "✍️ Daily Practice":
    st.title("✍️ Daily English Writing Challenge")
    st.write("Welcome to your daily English writing space!")

    col_name, col_email = st.columns([1, 1])
    with col_name:
        raw_name = st.text_input(
            "👤 Name / 姓名:", key="student_name_input", placeholder="e.g. Aiden"
        )
    with col_email:
        raw_email = st.text_input(
            "📧 Email / 邮箱:",
            key="student_email_input",
            placeholder="e.g. aiden@example.com",
        )

    student_name = raw_name.strip() if raw_name.strip() else "Student"
    student_email = raw_email.strip().lower()

    # Show subtle pool status so students/parents know how many fresh topics remain
    master_bank = load_topic_bank()
    all_history = load_history()
    done_count = (
        len({
            item["topic"]
            for item in all_history
            if item.get("email", "").strip().lower() == student_email
        })
        if student_email
        else 0
    )
    remaining_count = max(0, len(master_bank) - done_count)

    st.markdown("---")
    st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")
    if student_email:
        st.caption(
            f"🗂️ Topic Bank Status: **{remaining_count}** fresh topics left for {student_name} (Auto-adds +35 when ≤ 5 left)"
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button(
            "🔄 New Topic (Keep for later)",
            on_click=handle_new_topic,
            use_container_width=True,
        )
    with col2:
        st.button(
            "❌ Not Interested (Skip topic)",
            on_click=handle_skip_topic,
            use_container_width=True,
        )

    st.markdown("---")

    with st.form(key="writing_submission_form"):
        user_input = st.text_area(
            f"✍️ Write your response below, {student_name}! (Aim for 100-200 words):",
            key="writing_draft",
            height=240,
            placeholder="Start typing your entry here...",
        )

        word_count = len(user_input.split()) if user_input.strip() else 0
        st.caption(f"📝 Word Count: **{word_count} / 200** words")

        submit_pressed = st.form_submit_button(
            "🚀 Submit & Grade", use_container_width=True
        )

    def send_email_to_parent(name, topic, student_text, ai_feedback):
        sender = st.secrets.get("EMAIL_SENDER", "")
        password = st.secrets.get("EMAIL_PASSWORD", "")
        receiver = st.secrets.get("EMAIL_RECEIVER", "")

        if not sender or not password or not receiver:
            return False, "Email credentials missing."

        try:
            msg = MIMEMultipart()
            msg["From"] = f"Daily Writing App <{sender}>"
            msg["To"] = receiver
            msg["Subject"] = f"📝 Daily Writing Submission from {name}"

            body = f"""Hi,

{name} has just submitted a new writing practice!

👤 Student: {name}
📧 Email: {student_email}

📌 Topic:
{topic}

✍️ {name}'s Submission:
{student_text}

--------------------------------------------------
🤖 AI Teacher Feedback & Review:
{ai_feedback}

---
Sent automatically by Daily English Writing Challenge App.
"""
            msg.attach(MIMEText(body, "plain", "utf-8"))

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            return True, "Email sent successfully!"
        except Exception as e:
            return False, str(e)

    if submit_pressed:
        if not raw_name.strip():
            st.warning("⚠️ Please enter your name in the box above before submitting!")
        elif not raw_email.strip():
            st.warning(
                "⚠️ Please enter your email address in the box above to record your portfolio!"
            )
        elif not user_input.strip():
            st.warning("⚠️ Please write something in the text area before submitting!")
        elif not api_key:
            st.error("⚠️ GEMINI_API_KEY Missing in Streamlit Secrets!")
        else:
            with st.spinner(
                f"🎨 Your teacher is reading {student_name}'s letter... Please wait a few seconds!"
            ):
                try:
                    client = genai.Client(api_key=api_key)

                    prompt = f"""
                    You are an encouraging, inspiring Grade 5 English teacher in Canada.
                    Review this response by ESL student: {student_name}.

                    Topic: "{st.session_state.topic}"
                    Student Writing: "{user_input}"
                    Word Count: {word_count} words.

                    Provide feedback strictly in English formatted in Markdown:
                    ### 📊 Score & Overall Impression
                    * **Overall Score**: [X]/10
                    * **Grammar & Spelling**: [X]/5
                    * **Vocabulary & Word Choice**: [X]/5
                    * **Content Expansion & Details**: [X]/5

                    ### 🌟 What You Did Great
                    - Point 1
                    - Point 2

                    ### ✏️ Corrections & Improvements
                    - **Original**: "[Original sentence]"
                    - **Correction**: "[Corrected sentence]"
                    - **Why**: [Brief explanation]

                    ### 💡 How to Expand Your Writing (Break 100 Words!)
                    Give 3 concrete ways to add more content.

                    ### 🚀 Model Expansion (Example Version: 100-120 Words)
                    Rewrite ideas into a model 100-120 word paragraph.
                    """

                    models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
                    full_feedback = None
                    last_error = None

                    for model_name in models_to_try:
                        for attempt in range(2):
                            try:
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=prompt,
                                )
                                full_feedback = response.text
                                break
                            except Exception as e:
                                last_error = e
                                err_str = str(e).lower()
                                if (
                                    "503" in err_str
                                    or "overloaded" in err_str
                                    or "unavailable" in err_str
                                ):
                                    time.sleep(2)
                                    continue
                                else:
                                    break
                        if full_feedback:
                            break

                    if not full_feedback:
                        try:
                            available_flash = [
                                m.name.replace("models/", "")
                                for m in client.models.list()
                                if "flash" in m.name.lower()
                                and "lite" not in m.name.lower()
                                and "image" not in m.name.lower()
                                and "audio" not in m.name.lower()
                            ]
                            if available_flash:
                                available_flash.sort(reverse=True)
                                response = client.models.generate_content(
                                    model=available_flash[0],
                                    contents=prompt,
                                )
                                full_feedback = response.text
                        except Exception as fallback_e:
                            last_error = fallback_e

                    if not full_feedback:
                        raise last_error

                    st.markdown("### 📝 AI Teacher's Evaluation:")
                    st.markdown(full_feedback)
                    st.success(f"🎉 Great job, {student_name}! Review Completed!")

                    save_submission(
                        student_name,
                        student_email,
                        st.session_state.topic,
                        user_input,
                        full_feedback,
                    )
                    send_email_to_parent(
                        student_name,
                        st.session_state.topic,
                        user_input,
                        full_feedback,
                    )
                    st.toast("📧 Saved to Google Sheets & notification sent!")

                    # Check if uncompleted topics dropped to <= 5 after this submission
                    get_available_topics(
                        student_email=student_email, auto_replenish=True
                    )

                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg:
                        st.error(
                            "⚠️ The teacher has reached the daily limit. Please try again later!"
                        )
                    elif "503" in err_msg or "overloaded" in err_msg.lower():
                        st.warning(
                            "⏳ The teacher is busy right now. Your writing is still here. Please wait one minute and press Submit again."
                        )
                    else:
                        st.warning(
                            "⏳ Something interrupted the connection. Your writing is safe—please press Submit again."
                        )
                    with st.expander("Details for parent"):
                        st.code(err_msg)

# ---------------------------------------------------------
# PAGE 2: Writing History (Portfolio)
# ---------------------------------------------------------
elif page == "📚 Writing History":
    st.title("📚 Student Writing Portfolio & History")
    st.write(
        "Enter your email address to view all your past writing entries and AI feedback!"
    )

    search_email = (
        st.text_input(
            "📧 Enter your email to search / 输入邮箱查询历史记录:",
            placeholder="e.g. aiden@example.com",
        )
        .strip()
        .lower()
    )

    if search_email:
        all_history = load_history(force_refresh=True)
        user_records = [
            rec for rec in all_history if rec.get("email") == search_email
        ]

        if not user_records:
            st.info(
                f"No writing entries found for `{search_email}` yet. Go complete a daily challenge!"
            )
        else:
            user_records.reverse()
            st.success(
                f"Found {len(user_records)} writing entries for `{search_email}`!"
            )

            st.markdown("---")
            st.subheader("📋 Select an Entry to View Details:")

            options = [
                f"[{rec['timestamp']}] {rec['topic'][:50]}..."
                for rec in user_records
            ]

            selected_option = st.selectbox(
                "Choose a submission date / 选择提交记录:", options=options
            )

            selected_index = options.index(selected_option)
            selected_record = user_records[selected_index]

            st.markdown("---")
            st.markdown(f"### 📌 Topic: {selected_record['topic']}")
            st.caption(
                f"👤 **Student**: {selected_record['student_name']} | 📅 **Submitted At**: {selected_record['timestamp']}"
            )

            with st.expander("✍️ View Original Student Writing", expanded=True):
                st.write(selected_record["user_input"])

            with st.expander(
                "🤖 View AI Teacher Evaluation & Review", expanded=True
            ):
                st.markdown(selected_record["ai_feedback"])
