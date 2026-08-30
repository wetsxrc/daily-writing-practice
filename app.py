import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import google.generativeai as genai
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Grade 5 Daily Writing", page_icon="✍️", layout="centered"
)

st.title("✍️ Daily English Writing Challenge")
st.write("Welcome to your daily English writing space!")

# Fetch Gemini API Key
api_key = st.secrets.get("GEMINI_API_KEY", "")


# ---------------------------------------------------------
# Dynamic Topic Generation via Gemini AI
# ---------------------------------------------------------
def generate_ai_topic():
    if not api_key:
        # Fallback topic if API key is missing
        return "Describe your ideal weekend adventure with your family or friends."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.6-flash")

        topic_prompt = """
        Generate 1 creative, engaging, and age-appropriate daily English writing prompt for Grade 5 ESL students in Canada.
        
        Requirements:
        - Theme: Fun, relatable, imaginative, or school/life-related (e.g., pets, mysterious discoveries, space, rules, favorite foods, hobbies).
        - Length: Exactly 1 or 2 clear sentences.
        - Tone: Encouraging and easy to understand for 10-11 year olds.
        - Output format: Return ONLY the prompt text, no intro, no bullet points, and no quotes.
        """

        response = model.generate_content(topic_prompt)
        return response.text.strip()
    except Exception:
        # Fallback default list if API network call encounters an issue
        fallback_list = [
            "If you could invent a new subject to learn at school, what would it be and why?",
            "Imagine you woke up today with the superpower to fly. Describe your first flight!",
            "What is the best gift you have ever given or received? Why was it special?",
            "If you could build a secret hideout anywhere, where would it be and what inside?",
        ]
        return random.choice(fallback_list)


# Function to handle button click for new topic
def refresh_topic():
    st.session_state.topic = generate_ai_topic()


# Initialize Topic in Session State if not set
if "topic" not in st.session_state:
    st.session_state.topic = generate_ai_topic()

# ---------------------------------------------------------
# Student Name Input
# ---------------------------------------------------------
raw_name = st.text_input(
    "👤 Enter your name / 请输入你的名字:",
    placeholder="e.g. Aiden or Ethan",
    help="Type your name so we can personalize your review!",
)

# Fallback to "Student" if left empty
student_name = raw_name.strip() if raw_name.strip() else "Student"

st.markdown("---")

# Display Current AI-Generated Topic
st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")

# New Topic Button triggers AI dynamic generation
st.button("🔄 Generate New Topic", on_click=refresh_topic)

st.markdown("---")


# ---------------------------------------------------------
# Function to send email notification to parent
# ---------------------------------------------------------
def send_email_to_parent(name, topic, student_text, ai_feedback):
    sender = st.secrets.get("EMAIL_SENDER", "")
    password = st.secrets.get("EMAIL_PASSWORD", "")
    receiver = st.secrets.get("EMAIL_RECEIVER", "")

    if not sender or not password or not receiver:
        return False, "Email credentials not configured in Streamlit Secrets."

    try:
        msg = MIMEMultipart()
        msg["From"] = f"Daily Writing App <{sender}>"
        msg["To"] = receiver
        msg["Subject"] = f"📝 Daily Writing Submission from {name}"

        body = f"""Hi,

{name} has just submitted a new writing practice!

👤 Student: {name}

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


# ---------------------------------------------------------
# 3. Input Text Area and Word Count Limit
# ---------------------------------------------------------
user_input = st.text_area(
    f"✍️ Write your response below, {student_name}! (Max 200 words):",
    height=200,
    placeholder="Start typing your entry here...",
)

# Real-time word count calculation
word_count = len(user_input.split()) if user_input.strip() else 0

if word_count > 200:
    st.error(
        f"⚠️ Word count: {word_count} words. You have exceeded the 200-word limit! Please shorten your text."
    )
else:
    st.caption(f"📝 Word Count: **{word_count} / 200** words")

# ---------------------------------------------------------
# 4. Submit & Grading Logic
# ---------------------------------------------------------
if st.button("🚀 Submit & Grade"):
    if not user_input.strip():
        st.warning("Please write something before submitting!")
    elif word_count > 200:
        st.warning("Please shorten your text to 200 words or less!")
    elif not api_key:
        st.error(
            "API Key is missing. Please configure GEMINI_API_KEY in your Streamlit Secrets!"
        )
    else:
        with st.spinner(f"Your AI teacher is reading {student_name}'s writing..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                prompt = f"""
                You are an encouraging, warm, and friendly Grade 5 English teacher in Canada.
                Review the following writing response submitted by an ESL Grade 5 student named {student_name}.

                Topic Prompt: "{st.session_state.topic}"
                Student Writing: "{user_input}"

                Please provide feedback strictly in English, formatted in Markdown as follows:

                ### 📊 Score & Overall Impression
                * **Overall Score**: [X]/10
                * **Grammar & Spelling**: [X]/5
                * **Vocabulary**: [X]/5
                * **Ideas & Relevance**: [X]/5

                ### 🌟 What You Did Great
                - Point 1 (Highlight a good sentence or clever idea)
                - Point 2 (Highlight effective vocabulary usage)

                ### ✏️ Corrections & Improvements
                List any grammar or spelling mistakes clearly using this format:
                - **Original**: "[Original sentence with error]"
                - **Correction**: "[Corrected sentence]"
                - **Why**: [Brief, simple explanation suitable for Grade 5]

                ### 🚀 Level-Up Suggestion
                Provide 1 or 2 upgraded sentence structures or higher-level vocabulary words that could make this writing even better.
                """

                response = model.generate_content(prompt)
                ai_feedback = response.text

                st.success(f"🎉 Great job, {student_name}! Review Completed!")
                st.markdown(ai_feedback)

                # Send email notification quietly
                email_success, email_msg = send_email_to_parent(
                    student_name, st.session_state.topic, user_input, ai_feedback
                )
                if email_success:
                    st.toast(f"📧 Sent {student_name}'s writing to parent's email!")
                else:
                    st.caption(f"ℹ️ (Email notification status: {email_msg})")

            except Exception as e:
                st.error(f"An error occurred during review: {e}")
