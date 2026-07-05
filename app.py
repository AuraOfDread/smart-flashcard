import streamlit as st
import re
import random
import json
import requests
import os
from io import BytesIO

try:
    import pypdf
    import docx
    import google.generativeai as genai
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    st.error("Missing dependencies! Please run: pip install pypdf python-docx google-generativeai firebase-admin requests")

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
if "user" not in st.session_state:
    st.session_state.user = None
if "current_deck_title" not in st.session_state:
    st.session_state.current_deck_title = ""
if "score_saved" not in st.session_state:
    st.session_state.score_saved = False

api_from_config = ""
web_api_from_config = ""
service_account_from_config = None

if os.path.exists("config.json"):
    try:
        with open("config.json", "r") as f:
            config_data = json.load(f)
        api_from_config = config_data.get("secure_api_key", "")
        web_api_from_config = config_data.get("firebase_web_api_key", "")
        if "firebase_service_account" in config_data:
            service_account_from_config = dict(config_data["firebase_service_account"])
            if "private_key" in service_account_from_config:
                service_account_from_config["private_key"] = service_account_from_config["private_key"].replace("\\n", "\n")
    except Exception as parse_error:
        st.error(f"Error reading config.json configuration file: {parse_error}")

st.sidebar.title("Configuration 🛠️")

if api_from_config:
    active_api_key = api_from_config
    st.sidebar.markdown("🟢 **Gemini AI:** JSON Keys Active")
else:
    st.sidebar.text_input("Enter Gemini API Key:", type="password", key="manual_gemini_key")
    active_api_key = st.session_state.get("manual_gemini_key", "")

if web_api_from_config:
    active_web_key = web_api_from_config
    st.sidebar.markdown("🟢 **Firebase Auth:** JSON Keys Active")
else:
    st.sidebar.text_input("Enter Firebase Web API Key:", type="password", key="manual_firebase_web_key")
    active_web_key = st.session_state.get("manual_firebase_web_key", "")

db = None
if service_account_from_config:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_from_config)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        st.sidebar.markdown("🟢 **Firestore Database:** Connected")
    except Exception as e:
        st.sidebar.markdown("🔴 **Firestore Database:** Connection Error")
        st.sidebar.error(f"Details: {e}")
else:
    st.sidebar.markdown("🔴 **Firestore Database:** Credentials Missing")
    st.sidebar.warning("Add the missing file keys to your config.json file to clear this warning.")

def firebase_auth(email, password, mode):
    if not active_web_key:
        return {"error": {"message": "Firebase Web API Key is missing! Provide it via JSON parameters."}}
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{mode}?key={active_web_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"error": {"message": f"Connection Failure: {e}"}}

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
            The 'answer' field must be the exact missing word or short phrase that fills that blank contextually.
            """
        elif card_style == "Standard Q&A":
            style_instruction = """
            Every single flashcard must be in a direct question-and-answer format.
            The 'question' field must be an explicit question sentence.
            The 'answer' field must be a short, direct answer.
            """
        else:
            style_instruction = """
            Provide a healthy, randomized mix of both direct question-and-answer formats and fill-in-the-blank formats.
            For direct questions, use this style: "question": "Question text here?", "answer": "Answer text"
            For fill-in-the-blanks, use this style exactly: "question": "Fill in the blank:<br><br>Sentence text with ________.", "answer": "Answer text"
            """

        prompt = f"""
        You are an expert tutor. Analyze the following text. 
        Extract between 5 to 12 meaningful, highly accurate conceptual flashcard elements based strictly on the text context.
        Focus on important plot points, character actions, definitions, or critical concepts.
        
        Style Requirement:
        {style_instruction}
        
        The answers must be concise (1-7 words maximum) so they function perfectly within a Multiple Choice Quiz dashboard layout.
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

if st.session_state.user is None:
    st.title("🧠 SMART-PARSING STUDY")
    st.caption("Sign in to your account to track metrics and synchronize study sets across devices.")
    
    auth_choice = st.radio("Account Action", ["Log In", "Create Account"], horizontal=True)
    auth_email = st.text_input("Email Address")
    auth_password = st.text_input("Password", type="password")
    
    if auth_choice == "Log In":
        if st.button("Sign In Securely", type="primary", use_container_width=True):
            res = firebase_auth(auth_email, auth_password, "signInWithPassword")
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                st.session_state.user = res
                st.rerun()
    else:
        if st.button("Register Account", type="primary", use_container_width=True):
            res = firebase_auth(auth_email, auth_password, "signUp")
            if "error" in res:
                st.error(res["error"]["message"])
            else:
                st.success("Account constructed successfully! Switching layout... please login.")

else:
    st.sidebar.success(f"Logged in as: {st.session_state.user['email']}")
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        st.session_state.user = None
        st.session_state.cards = []
        st.rerun()
        
    st.title("🧠 SMART-PARSING STUDY")
    st.caption("The ultimate high-accuracy AI study suite powered by Gemini and Firebase.")

    workspace_action = st.radio(
        "Study Set Engine Mode", 
        ["Load Existing Saved Set", "Create New Study Set", "📊 Performance Analytics Dashboard"], 
        horizontal=True
    )
    st.divider()

    if workspace_action == "Load Existing Saved Set":
        if db is None:
            st.error("Cannot fetch cloud database data because your Firestore credentials are missing or broken.")
        else:
            try:
                sets_ref = db.collection("study_sets").where("user_id", "==", st.session_state.user["localId"]).stream()
                saved_decks = {doc.to_dict()["title"]: doc.to_dict()["cards"] for doc in sets_ref}
                
                if saved_decks:
                    selected_deck_title = st.selectbox("Select Cloud Deck to Activate:", list(saved_decks.keys()))
                    if st.button("📥 Import Active Deck Memory", type="primary", use_container_width=True):
                        st.session_state.cards = saved_decks[selected_deck_title]
                        st.session_state.current_deck_title = selected_deck_title
                        st.session_state.current_index = 0
                        st.session_state.flipped = False
                        st.session_state.quiz_score = 0
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_options = []
                        st.session_state.score_saved = False
                        st.success(f"Successfully loaded deck: {selected_deck_title}")
                        st.rerun()
                else:
                    st.info("No saved study sets discovered inside your cloud account partition.")
            except Exception as e:
                st.error(f"Error compiling structural lists from Firestore: {e}")

    elif workspace_action == "📊 Performance Analytics Dashboard":
        if db is None:
            st.error("Database connection unavailable to render metrics summary analytics layouts.")
        else:
            st.subheader("📊 Live Cloud Database Analytics")
            st.markdown("This control center queries your personal Firebase document collection schema live to generate student metrics reports.")
            
            try:
                decks_stream = db.collection("study_sets").where("user_id", "==", st.session_state.user["localId"]).stream()
                total_decks_count = len([d for d in decks_stream])
                
                scores_ref = db.collection("user_scores").where("user_id", "==", st.session_state.user["localId"]).stream()
                raw_scores = [doc.to_dict() for doc in scores_ref]
                
                if raw_scores:
                    total_quizzes = len(raw_scores)
                    total_pct = sum([(s["score"] / s["total"]) * 100 for s in raw_scores])
                    avg_performance = round(total_pct / total_quizzes, 1)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Decks Generated", f"{total_decks_count} Sets")
                    c2.metric("Quizzes Attempted", f"{total_quizzes} Runs")
                    c3.metric("Average Accuracy", f"{avg_performance}%")
                    
                    st.markdown("### 📋 Historic Database Records")
                    display_records = []
                    for row in raw_scores:
                        pct_string = f"{round((row['score'] / row['total']) * 100, 1)}%"
                        display_records.append({
                            "Study Set Title Target": row.get("deck_title", "Unknown Set"),
                            "Correct Answers Logged": row.get("score", 0),
                            "Total Card Pool Matrix": row.get("total", 0),
                            "Accuracy Rating Yield": pct_string
                        })
                    st.dataframe(display_records, use_container_width=True)
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Decks Generated", f"{total_decks_count} Sets")
                    c2.metric("Quizzes Attempted", "0 Runs")
                    c3.metric("Average Accuracy", "0.0%")
                    st.info("No quiz scores recorded inside the user scores cloud matrix partitions yet. Finish a multiple choice run to populate data.")
            except Exception as analytic_fault:
                st.error(f"Database query error compiling visual metrics: {analytic_fault}")

    else:
        with st.expander("📥 Import New Study Material (Text, PDF, or Word)", expanded=not bool(st.session_state.cards)):
            input_method = st.radio("Choose Input Method:", ["Manual Text Paste", "Upload Document File"], horizontal=True)
            card_style = st.selectbox("Select Flashcard Generation Style:", ["Standard Q&A", "Fill in the Blanks", "Mixed Mode (Both)"], index=0)
            
            final_text = ""
            deck_name_placeholder = "Manual Paste Deck"
            
            if input_method == "Manual Text Paste":
                final_text = st.text_area("Paste your narrative chapters, novels, or notes here:", height=180)
            else:
                uploaded_file = st.file_uploader("Upload any document (.pdf or .docx)", type=["pdf", "docx"])
                if uploaded_file is not None:
                    file_bytes = uploaded_file.read()
                    deck_name_placeholder = uploaded_file.name
                    if uploaded_file.name.endswith(".pdf"):
                        final_text = parse_pdf(file_bytes)
                    elif uploaded_file.name.endswith(".docx"):
                        final_text = parse_docx(file_bytes)
                    if final_text:
                        st.success(f"Successfully extracted context from '{uploaded_file.name}'!")

            if st.button("✨ Build Study Set with AI", type="primary", use_container_width=True):
                if not active_api_key.strip():
                    st.error("Please ensure you provide a valid Gemini API Key in the configuration module.")
                elif final_text.strip():
                    with st.spinner("🧠 AI is analyzing your text and writing flashcards..."):
                        generated, error_msg = generate_cards_with_ai(final_text, active_api_key.strip(), card_style)
                        
                    if error_msg:
                        st.error(f"❌ Google API Error: {error_msg}")
                    elif len(generated) >= 2:
                        st.session_state.cards = generated
                        st.session_state.current_deck_title = deck_name_placeholder
                        st.session_state.current_index = 0
                        st.session_state.flipped = False
                        st.session_state.quiz_score = 0
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_options = []
                        st.session_state.score_saved = False
                        
                        if db is not None:
                            try:
                                db.collection("study_sets").add({
                                    "user_id": st.session_state.user["localId"],
                                    "title": deck_name_placeholder,
                                    "cards": generated,
                                    "style": card_style
                                })
                                st.toast("Logged newly computed flashcard deck context parameters to Cloud Firestore!", icon="☁️")
                            except Exception as cloud_err:
                                st.warning(f"Flashcards generated successfully, but cloud database sync failed: {cloud_err}")
                        
                        st.rerun()
                    else:
                        st.warning("AI was unable to compile operational tokens. Ensure contextual variations populate inputs.")
                else:
                    st.error("Please enter text or upload a document to proceed.")

    if workspace_action != "📊 Performance Analytics Dashboard" and st.session_state.cards:
        total_cards = len(st.session_state.cards)
        st.markdown(f"### Current Workspace: **{st.session_state.current_deck_title}**")
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
                if not st.session_state.score_saved and db is not None:
                    try:
                        db.collection("user_scores").add({
                            "user_id": st.session_state.user["localId"],
                            "deck_title": st.session_state.current_deck_title,
                            "score": st.session_state.quiz_score,
                            "total": total_cards
                        })
                        st.session_state.score_saved = True
                        st.toast("Metrics synced successfully with the cloud environment!", icon="☁️")
                    except Exception as score_err:
                        st.error(f"Metrics synchronization fault detected: {score_err}")

                if st.button("🔄 Restart Quiz", use_container_width=True):    
                    st.session_state.current_index = 0    
                    st.session_state.quiz_score = 0    
                    st.session_state.quiz_answered = False    
                    st.session_state.quiz_options = []    
                    st.session_state.score_saved = False
                    st.rerun()
