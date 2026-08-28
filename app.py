import random
import google.generativeai as genai
import streamlit as st

# 1. 页面基本配置
st.set_page_config(
    page_title="Grade 5 Daily Writing", page_icon="✍️", layout="centered"
)

st.title("✍️ Daily English Writing Challenge")
st.write("欢迎来到每日英文写作小天地！")

# 2. 启发式 Topic 库（贴合加拿大 5 年级孩子生活与想象力）
TOPIC_BANK = [
    "If you could create one new rule for recess at your school, what would it be and why?",
    "Describe your favorite afternoon snack using as many sensory words (sight, smell, taste) as possible.",
    "If your pet or a favourite animal could talk for 10 minutes, what questions would you ask it?",
    "What was the most interesting thing that happened in your class or school this week?",
    "Imagine you found a mysterious small key in your room. What hidden box or room does it open?",
    "What is your favorite outdoor activity to play with friends, and how do you play it?",
    "If you could travel anywhere in Canada tomorrow, where would you go and what would you do there?",
    "If you could design a new video game or board game, what would the goal of the game be?",
]

# 初始化随机题目
if "topic" not in st.session_state:
    st.session_state.topic = random.choice(TOPIC_BANK)

# 展现当前题目
st.info(f"📌 **Today's Topic:**\n\n### {st.session_state.topic}")

if st.button("🔄 换一个题目 (New Topic)"):
    st.session_state.topic = random.choice(TOPIC_BANK)

st.markdown("---")

# 3. 输入框与 200 字限制
user_input = st.text_area(
    "✍️ Write your story or answer below (Max 200 words):",
    height=200,
    placeholder="Start typing your email response here...",
)

# 实时统计字数
word_count = len(user_input.split()) if user_input.strip() else 0

if word_count > 200:
    st.error(f"⚠️ 当前字数：{word_count} 字。已经超过 200 字上限，请稍微删除一点内容哦！")
else:
    st.caption(f"📝 Word Count: **{word_count} / 200** words")

# 4. 获取网页后台配置的 Gemini API Key
api_key = st.secrets.get("GEMINI_API_KEY", "")

# 5. 提交与 AI 批改逻辑
if st.button("🚀 Submit & Grade (提交批改)"):
    if not user_input.strip():
        st.warning("Please write something before submitting! (请先输入内容再提交)")
    elif word_count > 200:
        st.warning("Please shorten your text to 200 words or less! (请先修改至 200 字以内)")
    elif not api_key:
        st.error("后台未配置 GEMINI_API_KEY，请在 Streamlit Secrets 中配置！")
    else:
        with st.spinner("AI 老师正在认真阅读并批改中，请稍等..."):
            try:
                genai.configure(api_key=api_key)
                # 使用标准的 Flash 模型
                model = genai.GenerativeModel("gemini-1.5-flash")

                prompt = f"""
                You are an encouraging, warm, and friendly Grade 5 English teacher in Canada.
                Review the following writing response submitted by an ESL student (Grade 5 level).

                Topic Prompt: "{st.session_state.topic}"
                Student Writing: "{user_input}"

                Please provide feedback strictly formatted in Markdown as follows:

                ### 📊 Score & Overall Impression
                * **Overall Score**: [X]/10
                * **Grammar & Spelling**: [X]/5
                * **Vocabulary**: [X]/5
                * **Ideas & Relevance**: [X]/5

                ### 🌟 What You Did Great (闪光点)
                - Point 1 (Highlight a good sentence or clever idea)
                - Point 2 (Highlight good vocabulary usage)

                ### ✏️ Corrections & Improvements (语法修改)
                List any grammar or spelling mistakes clearly using this format:
                - **Original**: "[Original sentence with error]"
                - **Correction**: "[Corrected sentence]"
                - **Why**: [Brief simple explanation suitable for Grade 5]

                ### 🚀 Level-Up Suggestion (进阶表达)
                Show 1 or 2 upgraded sentence structures or higher-level vocabulary words that could make this writing even better.
                """

                response = model.generate_content(prompt)
                st.success("🎉 批改完成！")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"批改过程中出现错误：{e}")
