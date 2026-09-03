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
# Initial Default Topic Bank (Fast Loading Base)
# ---------------------------------------------------------
INITIAL_TOPIC_BANK = [
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
    "Imagine you are building a time machine. Which period in history would you visit first?",
    "If you had $100 to spend on making your community a better place, how would you use it?",
    "Describe what your dream bedroom would look like if you had an unlimited budget.",
    "If you could invent a new flavor of ice cream, what ingredients would you put in it?",
    "What is your favorite book or story, and what makes it so exciting to read?",
    "If animals could go to school just like humans, which animal do you think would be the smartest student?",
]


# Function to background-expand the topic bank using Gemini AI
def replenish_topic_bank_with_ai():
    if not api_key:
        return

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.6-flash")

        prompt = """
        Generate 15 creative, fun, and age-appropriate writing prompts for Grade 5 ESL students in Canada.
        Requirements:
        - Diverse topics (imagination, school life, hobbies, animals, adventures, nature).
        - Easy to understand for 10-11 year olds.
        - Output ONLY a bulleted list of prompts, one per line, without any extra text or header.
        - Format each prompt starting with a dash, like this:
        - Prompt 1
        - Prompt 2
        """

        response = model.generate_content(prompt)
        raw_lines = response.text.strip().split("\n")

        new_prompts = []
        for line in raw_lines:
            line = line.strip().lstrip("-*• ").strip()
            if line and line not in st.session_state.topic_bank:
                new_prompts.append(line)

        st.session_state.topic_bank.extend(new_prompts)
    except Exception:
        pass


# ---------------------------------------------------------
# Initialize State for Topics
# ---------------------------------------------------------
if "topic_bank" not in st.session_state:
    st.session_state.topic_bank = INITIAL_TOPIC_BANK.copy()


def pick_random_topic():
    if len(st.session_state.topic_bank) < 10:
        replenish_topic_bank_with_ai()

    if not st.session_state.topic_bank:
        st.session_state.topic_bank = INITIAL_TOPIC_BANK.copy()

    current = st.session_state.get("topic")
    candidates = [t for t in st.session_state.topic_bank if t != current]

    if candidates:
        return random.choice(candidates)
    return random.choice(st.session_state.topic_bank)


if "topic" not in st.session_state:
    st.session_state.topic = pick_random_topic()


def switch_to_next_topic():
    st.session_state.topic = pick_random_topic()


# ---------------------------------------------------------
# Student Name Input
# ---------------------------------------------------------
raw_name = st.text_input(
    "👤 Enter your name / 请输入你的名字:",
    placeholder="e.g. Aiden or Ethan",
    help="Type your name so we can personalize your review!",
)

student_name = raw_name.strip() if raw_name.strip() else "Student"

st.markdown("---")

st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")
st.button("🔄 New Topic", on_click=switch_to_next_topic)

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
# Input Text Area and Word Count Limit
# ---------------------------------------------------------
user_input = st.text_area(
    f"✍️ Write your response below, {student_name}! (Aim for 100-200 words):",
    height=220,
    placeholder="Start typing your entry here... Challenge yourself to reach at least 100 words by adding details, reasons, and feelings!",
)

word_count = len(user_input.split()) if user_input.strip() else 0

if word_count > 200:
    st.error(
        f"⚠️ Word count: {word_count} words. You have exceeded the 200-word limit! Please shorten your text."
    )
elif word_count > 0 and word_count < 50:
    st.warning(
        f"💡 Current Word Count: **{word_count}** words. Good start! Can you add more details or examples to break 100 words?"
    )
else:
    st.caption(f"📝 Word Count: **{word_count} / 200** words")

# ---------------------------------------------------------
# Submit & Grading Logic
# ---------------------------------------------------------
if st.button("🚀 Submit & Grade"):
    if not raw_name.strip():
        st.warning(
            "⚠️ Please enter your name before submitting! / 请先输入你的名字后再提交！"
        )
    elif not user_input.strip():
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
                You are an encouraging, inspiring, and friendly Grade 5 English teacher in Canada.
                Review the following writing response submitted by an ESL Grade 5 student named {student_name}.

                Topic Prompt: "{st.session_state.topic}"
                Student Writing: "{user_input}"
                Current Word Count: {word_count} words.

                Your main goal is to guide the student to EXPAND their writing to at least 100+ words using richer vocabulary, varied sentence structures, and vivid details.

                Please provide feedback strictly in English, formatted in Markdown as follows:

                ### 📊 Score & Overall Impression
                * **Overall Score**: [X]/10
                * **Grammar & Spelling**: [X]/5
                * **Vocabulary & Word Choice**: [X]/5
                * **Content Expansion & Details**: [X]/5

                ### 🌟 What You Did Great
                - Point 1 (Highlight a good sentence, creative idea, or vocabulary choice)
                - Point 2 (Highlight effort or clear thought)

                ### ✏️ Corrections & Improvements
                List any grammar, spelling, or punctuation mistakes clearly:
                - **Original**: "[Original sentence with error]"
                - **Correction**: "[Corrected sentence]"
                - **Why**: [Brief, simple explanation suitable for Grade 5]

                ### 💡 How to Expand Your Writing (Break 100 Words!)
                Give {student_name} 3 concrete ways to add more content and reach 100+ words:
                1. **Add Sensory Details**: [Suggest specific sight, sound, or feeling details they could add]
                2. **Explain the 'Why' & Reasons**: [Suggest a question they can answer to explain their thoughts further]
                3. **Vocabulary & Sentence Upgrade**: Show how to turn one simple sentence from their text into a compound/complex sentence with higher-level adjectives/verbs.

                ### 🚀 Model Expansion (Example Version: 100-120 Words)
                Rewrite {student_name}'s original ideas into an expanded, high-level Grade 5 paragraph (~100-120 words). Keep their core story/idea, but enrich it with advanced vocabulary, transition words (e.g., Furthermore, Suddenly, As a result), and vivid details so they can learn by example.
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

                # Remove the completed topic ONLY AFTER successful submission
                completed_topic = st.session_state.topic
                if completed_topic in st.session_state.topic_bank:
                    st.session_state.topic_bank.remove(completed_topic)

            except Exception as e:
                st.error(f"An error occurred during review: {e}")
