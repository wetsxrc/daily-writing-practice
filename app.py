import random
import google.generativeai as genai
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Grade 5 Daily Writing", page_icon="✍️", layout="centered"
)

st.title("✍️ Daily English Writing Challenge")
st.write("Welcome to your daily English writing space!")

# 2. Daily Topic Pool (tailored for Grade 5 students in Canada)
TOPIC_BANK = [
    "If you could create one new rule for recess at your school, what would it be and why?",
    "Describe your favorite afternoon snack using as many sensory words (sight, smell, taste) as possible.",
    "If your pet or a favorite animal could talk for 10 minutes, what questions would you ask it?",
    "What was the most interesting thing that happened in your class or school this week?",
    "Imagine you found a mysterious small key in your room. What hidden box or room does it open?",
    "What is your favorite outdoor activity to play with friends, and how do you play it?",
    "If you could travel anywhere in Canada tomorrow, where would you go and what would you do there?",
    "If you could design a new video game or board game, what would the goal of the game be?",
]

# Initialize Topic
if "topic" not in st.session_state:
    st.session_state.topic = random.choice(TOPIC_BANK)

# Display Current Topic
st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")

st.button("🔄 New Topic", on_click=change_topic)

st.markdown("---")

# 3. Input Text Area and Word Count Limit
user_input = st.text_area(
    "✍️ Write your response below (Max 200 words):",
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

# 4. Fetch Gemini API Key from Streamlit Secrets
api_key = st.secrets.get("GEMINI_API_KEY", "")

# 5. Submit & Grading Logic
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
        with st.spinner("Your AI teacher is reading and reviewing..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-3.6-flash")

                prompt = f"""
                You are an encouraging, warm, and friendly Grade 5 English teacher in Canada.
                Review the following writing response submitted by an ESL Grade 5 student.

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
                st.success("🎉 Review Completed!")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"An error occurred during review: {e}")
