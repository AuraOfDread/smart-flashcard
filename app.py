import streamlit as st
import re
import random
import json
from io import BytesIO

try:
    import pypdf
    import docx
    import google.generativeai as genai
except ImportError:
    st.error("Missing dependencies! Please run: pip install pypdf python-docx google-generativeai")

st.set_page_config(page_title="SMART-PARSING STUDY", page_icon="🧠", layout="centered")

st.markdown("""
<style>
.flashcard-box {
    background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
    border-radius: 16px;
    padding: 40px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
    border: 1px solid #e2e8f0;
    text-align: center;
    min-height: 200px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    margin-bottom: 20px;
}
.card-text {
    font-size: 1.3rem !important;
    font-weight: 500;
    color: #1e293b;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)

st.title("🧠 SMART-PARSING STUDY")
st.caption("The ultimate high-accuracy AI study suite powered by Gemini.")

if "cards" not in st.session_state:
    st.session_state.cards = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "flipped" not in st.session_state:
    st.session_state.flipped = False
if "quiz_score" not in st.session_state:
    st.session_state.quiz_score = 0
if "quiz_answered" not in st.session_state:
    st.session_state.quiz_answered = False
if "quiz_options" not in st.session_state:
    st.session_state.quiz_options = []
if "previous_mode" not in st.session_state:
    st.session_state.previous_mode = "📇 Flashcards"

def parse_pdf(file_bytes):
    try:
        pdf_reader = pypdf.PdfReader(BytesIO(file_bytes))
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text
    except Exception as e:
        st.error(f"Error parsing PDF: {e}")
        return ""

def parse_docx(file_bytes):
    try:
        doc = docx.Document(BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        st.error(f"Error parsing Word Document: {e}")
        return ""

def generate_cards_with_ai(text, api_key, card_style):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        if card_style == "Fill in the Blanks":
            style_instruction = """
            Every single flashcard must be in a 'fill-in-the-blank' format. 
            The 'question' field must strictly start with the exact prefix 'Fill in the blank:<br><br>' followed by a complete sentence where a crucial keyword (like a character name, setting, core concept, or key term) has been replaced with '________'.
            Example: "question": "Fill in the blank:<br><br>The protagonist of the story is ________."
            The 'answer' field must be the exact missing word or short phrase that fills that blank contextually.
            Example: "answer": "Harry Potter"
            """
        elif card_style == "Standard Q&A":
            style_instruction = """
            Every single flashcard must be in a direct question-and-answer format.
            The 'question' field must be an explicit question sentence.
            Example: "question": "Who is the protagonist of the story?"
            The 'answer' field must be a short, direct answer.
            Example: "answer": "Harry Potter"
            """
        else:
            style_instruction = """
            Provide a healthy, randomized mix of both direct question-and-answer formats and fill-in-the-blank formats.
            For direct questions, use this style:
            "question": "Who is the protagonist of the story?", "answer": "Harry Potter"
            For fill-in-the-blanks, use this style exactly:
            "question": "Fill in the blank:<br><br>The protagonist of the story is ________.", "answer": "Harry Potter"
            """

        prompt = f"""
        You are an expert tutor. Analyze the following text (which could be a novel chapter, textbook content, or study notes). 
        Extract between 5 to 12 meaningful, highly accurate conceptual flashcard elements based strictly on the text context.
        Focus on important plot points, character actions, definitions, or critical concepts.
        
        Style Requirement:
        {style_instruction}
        
        Avoid trivial, overly generic, or uninformative choices. The answers must be concise (1-7 words maximum) so they function perfectly within a Multiple Choice Quiz dashboard layout.

        You MUST respond ONLY with a valid JSON array of objects. Do not add markdown blocks like ```json.
        Each object inside the list must have exactly two keys: "question" and "answer".
        
        Text to analyze:
        {text}
        """
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        cards_list = json.loads(response.text)
        return cards_list, None
        
    except Exception as e:
        return [], str(e)

st.sidebar.title("Configuration 🛠️")

has_secret_key = "secure_api_key" in st.secrets

if has_secret_key:
    active_api_key = st.secrets["secure_api_key"]
    st.sidebar.markdown("🟢 **Status:** System API Key Active")
    st.sidebar.info("Reading credentials securely from your local secrets configuration file.")
else:
    st.sidebar.text_input(
        "Enter Gemini API Key:", 
        type="password", 
        key="secure_api_key",
        help="Paste your key here. It saves automatically as you type."
    )
    st.sidebar.divider()
    
    if st.session_state.get("secure_api_key"):
        active_api_key = st.session_state.get("secure_api_key")
        st.sidebar.markdown("🟢 **Status:** Key Saved & Active")
    else:
        active_api_key = ""
        st.sidebar.markdown("🔴 **Status:** Missing API Key")

st.sidebar.markdown("[Get Free API Key Here](https://aistudio.google.com/)")

with st.expander("📥 Import Study Material (Text, PDF, or Word)", expanded=not bool(st.session_state.cards)):
    
    input_method = st.radio("Choose Input Method:", ["Manual Text Paste", "Upload Document File"], horizontal=True)
    
    card_style = st.selectbox(
        "Select Flashcard Generation Style:",
        ["Standard Q&A", "Fill in the Blanks", "Mixed Mode (Both)"],
        index=0,
        help="Choose how you want the AI to formulate your study pairs."
    )
    
    final_text = ""
    
    if input_method == "Manual Text Paste":
        final_text = st.text_area(
            "Paste your narrative chapters, novels, or notes here:",
            height=180,
            placeholder="Paste raw text here. The AI will read it conceptually and build perfect questions out of it."
        )
    else:
        uploaded_file = st.file_uploader("Upload any document (.pdf or .docx)", type=["pdf", "docx"])
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            if uploaded_file.name.endswith(".pdf"):
                final_text = parse_pdf(file_bytes)
            elif uploaded_file.name.endswith(".docx"):
                final_text = parse_docx(file_bytes)
            
            if final_text:
                st.success(f"Successfully extracted context from '{uploaded_file.name}'!")

    if st.button("✨ Build Study Set with AI", type="primary", use_container_width=True):
        
        if not active_api_key.strip():
            st.error("Please add a key to your secrets.toml file or input it manually via the sidebar text box!")
        elif final_text.strip():
            with st.spinner("🧠 AI is analyzing your text and writing flashcards..."):
                generated, error_msg = generate_cards_with_ai(final_text, active_api_key.strip(), card_style)
                
            if error_msg:
                st.error(f"❌ **Google API Error:** {error_msg}")
                st.info("💡 Double-check your API Key string value inside your secrets file or sidebar field for typos.")
            elif len(generated) >= 2:
                st.session_state.cards = generated
                st.session_state.current_index = 0
                st.session_state.flipped = False
                st.session_state.quiz_score = 0
                st.session_state.quiz_answered = False
                st.session_state.quiz_options = []
                st.rerun()
            else:
                st.warning("AI was unable to extract clear concepts. Please ensure your source text contains complete information blocks.")
        else:
            st.error("Please enter text or upload a document to proceed.")

if st.session_state.cards:
    total_cards = len(st.session_state.cards)
    study_mode = st.radio("Choose Study Mode:", ["📇 Flashcards", "📝 Multiple Choice Quiz"], horizontal=True)    
    
    if study_mode != st.session_state.previous_mode:
        st.session_state.previous_mode = study_mode
        st.session_state.quiz_options = []
        st.session_state.quiz_answered = False
        st.rerun()

    st.divider()    

    progress_percentage = (st.session_state.current_index + 1) / total_cards    
    st.progress(progress_percentage)    
    st.write(f"**Progress:** Card {st.session_state.current_index + 1} of {total_cards}")    

    if study_mode == "📇 Flashcards":    
        current_card = st.session_state.cards[st.session_state.current_index]    
            
        if not st.session_state.flipped:    
            st.markdown(f'<div class="flashcard-box"><p class="card-text">❓ {current_card["question"]}</p></div>', unsafe_allow_html=True)    
        else:    
            st.markdown(f'<div class="flashcard-box" style="background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);"><p class="card-text">💡 {current_card["answer"]}</p></div>', unsafe_allow_html=True)    

        col1, col2, col3 = st.columns([1, 2, 1])    
        with col1:    
            if st.button("⬅️ Back", disabled=(st.session_state.current_index == 0), use_container_width=True):    
                st.session_state.current_index -= 1    
                st.session_state.flipped = False    
                st.session_state.quiz_options = []
                st.session_state.quiz_answered = False
                st.rerun()    
        with col2:    
            flip_text = "🙈 Hide Answer" if st.session_state.flipped else "👀 Flip Card"    
            if st.button(flip_text, type="secondary", use_container_width=True):    
                st.session_state.flipped = not st.session_state.flipped    
                st.rerun()    
        with col3:    
            if st.button("Next ➡️", disabled=(st.session_state.current_index == total_cards - 1), use_container_width=True):    
                st.session_state.current_index += 1    
                st.session_state.flipped = False    
                st.session_state.quiz_options = []
                st.session_state.quiz_answered = False
                st.rerun()    

    elif study_mode == "📝 Multiple Choice Quiz":    
        current_card = st.session_state.cards[st.session_state.current_index]    
        correct_ans = current_card["answer"]    
            
        if not st.session_state.quiz_options:     
            all_answers = list(set([c["answer"] for c in st.session_state.cards]))    
            wrong_answers = [ans for ans in all_answers if ans.lower() != correct_ans.lower()]    
                
            num_distractors = min(3, len(wrong_answers))    
            if num_distractors > 0:
                sampled_distractors = random.sample(wrong_answers, num_distractors)    
            else:
                sampled_distractors = ["Alternative Option A", "Alternative Option B", "Alternative Option C"][:min(3, total_cards)]
                
            options = list(set(sampled_distractors + [correct_ans]))
            random.shuffle(options)    
            st.session_state.quiz_options = options    

        st.markdown(f'<div class="flashcard-box"><p class="card-text">{current_card["question"]}</p></div>', unsafe_allow_html=True)    
            
        user_choice = st.radio(
            "Select the correct answer:",    
            st.session_state.quiz_options,    
            index=None,    
            key=f"q_{st.session_state.current_index}",
            disabled=st.session_state.quiz_answered
        )    
            
        col1, col2 = st.columns(2)    
            
        with col1:    
            if st.button("✔️ Submit Answer", disabled=st.session_state.quiz_answered or user_choice is None, use_container_width=True, type="primary"):    
                st.session_state.quiz_answered = True    
                if user_choice == correct_ans:    
                    st.session_state.quiz_score += 1    
                    st.toast("🎉 Correct!", icon="✅")    
                else:    
                    st.toast("Whoops! Incorrect.", icon="❌")    
                st.rerun()    
                    
        with col2:    
            next_disabled = not st.session_state.quiz_answered or (st.session_state.current_index == total_cards - 1)    
            if st.button("Next Question ➡️", disabled=next_disabled, use_container_width=True):    
                st.session_state.current_index += 1    
                st.session_state.quiz_answered = False    
                st.session_state.quiz_options = []    
                st.rerun()    
                    
        if st.session_state.quiz_answered:    
            if user_choice == correct_ans:    
                st.success(f"🎯 **Correct!** The answer is indeed: {correct_ans}")    
            else:    
                st.error(f"😢 **Incorrect.** You selected '{user_choice}'. The right answer was: **{correct_ans}**")    
                    
        st.metric(label="Current Score", value=f"{st.session_state.quiz_score} / {total_cards}")    
            
        if st.session_state.current_index == total_cards - 1 and st.session_state.quiz_answered:    
            st.balloons()    
            if st.button("🔄 Restart Quiz", use_container_width=True):    
                st.session_state.current_index = 0    
                st.session_state.quiz_score = 0    
                st.session_state.quiz_answered = False    
                st.session_state.quiz_options = []    
                st.rerun()
