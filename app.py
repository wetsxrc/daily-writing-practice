import datetime
import json
import os
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import google.generativeai as genai
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Grade 5 Daily Writing & Portfolio",
    page_icon="✍️",
    layout="centered",
)

# Fetch Gemini API Key
api_key = st.secrets.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------
# Persistent Data Files
# ---------------------------------------------------------
HISTORY_FILE = "writing_history.json"


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_submission(student_name, email, topic, user_input, ai_feedback):
    history = load_history()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = {
        "student_name": student_name,
        "email": email.strip().lower(),
        "topic": topic,
        "user_input": user_input,
        "ai_feedback": ai_feedback,
        "timestamp": timestamp,
    }
    history.append(entry)

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Failed to save history record: {e}")


# ---------------------------------------------------------
# Initial Default Topic Bank
# ---------------------------------------------------------
INITIAL_TOPIC_BANK = [
    "Imagine you are building a time machine. Which period in history would you visit first?",
    "If you could create one new rule for recess at your school, what would it be and why?",
    "Describe your favorite afternoon snack using as many sensory words (sight, smell, taste) as possible.",
    "If your pet or a favorite animal could talk for 10 minutes, what questions would you ask it?",
    "What was the most interesting thing that happened in your class or school this week?",
    "Imagine you found a mysterious small key in your room. What hidden box or room does it open?",
    "What is your favorite outdoor activity to play with friends, and how do you play it?",
    "If you could travel anywhere in Canada tomorrow, where would you go and what would you do there?",
    "If you could design a new video game or board game, what would the goal of the game be?",
    "If you woke up tomorrow with the ability to turn invisible, what is the first thing you would do?",
    "Write about a time you tried something new. How did you feel before and after?",
    "If you could trade places with any character in a book or movie for one day, who would it be?",
    "What is the best piece of advice a family member or teacher has ever given you?",
    "If you had $100 to spend on making your community a better place, how would you use it?",
    "Describe what your dream bedroom would look like if you had an unlimited budget.",
]

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
history_records = load_history()
completed_topics_set = {item["topic"] for item in history_records}

if "topic_bank" not in st.session_state:
    st.session_state.topic_bank = [
        t for t in INITIAL_TOPIC_BANK if t not in completed_topics_set
    ]


def pick_random_topic():
    current_history = load_history()
    completed_set = {item["topic"] for item in current_history}

    st.session_state.topic_bank = [
        t for t in st.session_state.topic_bank if t not in completed_set
    ]

    if not st.session_state.topic_bank:
        st.session_state.topic_bank = [
            t for t in INITIAL_TOPIC_BANK if t not in completed_set
        ]

    current = st.session_state.get("topic")
    candidates = [t for t in st.session_state.topic_bank if t != current]

    if candidates:
        return random.choice(candidates)
    elif st.session_state.topic_bank:
        return random.choice(st.session_state.topic_bank)
    else:
        return "Imagine you are building a time machine. Which period in history would you visit first?"


if (
    "topic" not in st.session_state
    or st.session_state.topic in completed_topics_set
):
    st.session_state.topic = pick_random_topic()


def switch_to_next_topic():
    st.session_state.topic = pick_random_topic()


def remove_disliked_topic():
    disliked_topic = st.session_state.topic
    if disliked_topic in st.session_state.topic_bank:
        st.session_state.topic_bank.remove(disliked_topic)
    st.session_state.topic = pick_random_topic()


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

    # 快捷输入姓名与邮箱
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

    st.markdown("---")
    st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button(
            "🔄 New Topic (Keep for later)",
            on_click=switch_to_next_topic,
            use_container_width=True,
        )
    with col2:
        st.button(
            "❌ Not Interested (Skip topic)",
            on_click=remove_disliked_topic,
            use_container_width=True,
        )

    st.markdown("---")

    # 使用 st.form 确保点击 Submit 100% 触发后台 Python 逻辑，绝不卡死
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

    # 批改逻辑响应
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
                f"🎨 AI Teacher is reviewing {student_name}'s writing... Please wait a few seconds!"
            ):
                try:
                    genai.configure(api_key=api_key)
                    # 使用标准免费额度模型
                    model = genai.GenerativeModel("gemini-1.5-flash")

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

                    response = model.generate_content(prompt)
                    full_feedback = response.text

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
                    st.toast("📧 Saved to portfolio & notification sent!")

                except Exception as e:
                    if "429" in str(e):
                        st.error(
                            "⚠️ AI 老师今日免费批改次数已用完（429 Quota Exceeded）。请稍等或明天再试！"
                        )
                    else:
                        st.error(f"An error occurred during review: {e}")

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
        all_history = load_history()
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
