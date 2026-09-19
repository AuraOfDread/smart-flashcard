import streamlit as st
import json
import uuid
from google import genai
import PyPDF2
import pandas as pd

def render_teacher_dashboard(db, active_api_key):
    st.title("Teacher Studio: AI Assessment Builder")
    
    # ---------------------------------------------------------
    # STEP 1: DUAL INPUT (FILE UPLOAD OR COPY/PASTE)
    # ---------------------------------------------------------
    st.subheader("1. Provide Study Material")
    
    input_method = st.radio("Choose Input Method:", ["Upload PDF", "Paste Text"], horizontal=True)
    extracted_text = ""
    
    if input_method == "Upload PDF":
        uploaded_file = st.file_uploader("Upload PDF Document", type=["pdf"])
        if uploaded_file is not None:
            try:
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + "\n"
                # Scrub the text to prevent surrogate character API crashes
                extracted_text = extracted_text.encode('utf-8', 'ignore').decode('utf-8')
                st.success("Document text extracted successfully!")
            except Exception as e:
                st.error(f"Error reading document: {e}")
                
    else:
        extracted_text = st.text_area("Paste your study notes, articles, or text here:", height=200)
        if extracted_text:
            st.success("Text captured successfully!")

    # ---------------------------------------------------------
    # STEP 2: CONFIGURE & GENERATE
    # ---------------------------------------------------------
    if extracted_text:
        st.subheader("2. Configure Quiz")
        
        # --- NEW: The Quiz Title Input ---
        quiz_title = st.text_input("Enter Quiz Title (e.g., 'Unit 1: Process Scheduling')")
        
        difficulty = st.selectbox(
            "Select Difficulty Level", 
            ["Easy (True/False & Fill-in-Blanks)", "Standard (MCQs)", "Hard (Multi-Select & Spot the Error)"]
        )

        def generate_quiz(feedback=""):
            if "Easy" in difficulty:
                format_rule = "Generate 5 True/False and fill-in-the-blank questions. Format as JSON: [{'question': '...', 'type': 'tf', 'options': ['True', 'False'], 'answer': 'True'}, {'question': '...', 'type': 'fib', 'answer': 'exact word'}]"
            elif "Standard" in difficulty:
                format_rule = "Generate 5 standard multiple-choice questions. Format as JSON: [{'question': '...', 'type': 'mcq', 'options': ['Exact text of option 1', 'Exact text of option 2', 'Exact text of option 3', 'Exact text of option 4'], 'answer': 'Exact text of correct option'}]"
            else:
                format_rule = "Generate 5 Hard difficulty questions. 3 must be 'multi_select', 2 must be 'spot_error'. Format as JSON: [{'question': '...', 'type': 'multi_select', 'options': ['Exact text 1', 'Exact text 2', 'Exact text 3', 'Exact text 4'], 'answer': ['Exact text 1', 'Exact text 3']}, {'question': '...', 'type': 'spot_error', 'options': ['Para 1 text', 'Para 2 text', 'Para 3 text', 'Para 4 text'], 'answer': 'Para 2 text'}]"
                
            anti_ghosting = "CRITICAL RULES: 1. No image/figure questions. 2. The 'answer' value MUST identically match the exact string inside the 'options' array. DO NOT use letters (like 'A' or 'B') as the answer. DO NOT add prefixes (like 'Paragraph 3:') to the answer string."
            
            # --- THE FIX: AI Prompt Hierarchy ---
            # We put the feedback at the absolute TOP so the AI cannot ignore it
            instruction_header = "You are a strict JSON API."
            if feedback:
                instruction_header += f"\n\n🚨 URGENT TEACHER OVERRIDE: {feedback} 🚨\n(You MUST prioritize this instruction when selecting topics for the questions!)\n"
                
            final_prompt = f"{instruction_header}\n\n{format_rule}\n{anti_ghosting}\n\nSOURCE TEXT TO USE:\n{extracted_text}"
            
            with st.spinner("Gemini is generating questions..."):
                try:
                    client = genai.Client(api_key=active_api_key)
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=final_prompt
                    )
                    
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    elif raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]
                        
                    parsed_json = json.loads(raw_text.strip())
                    st.session_state['draft_quiz'] = parsed_json
                    st.success("Draft generated! Scroll down to review.")
                    
                except Exception as e:
                    st.error(f"Generation Error: {e}")

        if st.button("Generate First Draft"):
            generate_quiz()

   # ---------------------------------------------------------
    # STEP 3: REVIEW, ITERATE & PUBLISH
    # ---------------------------------------------------------
    if 'draft_quiz' in st.session_state:
        st.divider()
        st.subheader("3. Review Draft & Iterate")
        
        with st.expander("🛠️ Did AI miss a topic? Coach the AI to regenerate."):
            teacher_feedback = st.text_input("Type your instructions (e.g., 'Make sure to include a question about deadlocks'):")
            if st.button("Regenerate with Feedback"):
                # We removed st.rerun() here! Now the success message will stay visible 
                # and the UI won't aggressively flash and close your expander box!
                generate_quiz(feedback=teacher_feedback)
        
        st.write("### Current Draft Questions:")
        approved_questions = []
        
        for index, q in enumerate(st.session_state['draft_quiz']):
            q_type = q.get('type', 'mcq').replace('_', ' ').title()
            st.write(f"**Question {index + 1} ({q_type}):** {q.get('question', 'Unknown')}")
            
            if 'options' in q:
                st.write("**Generated Options:**")
                for opt in q['options']:
                    st.write(f"- {opt}")
            
            st.write(f"*Answer Key:* `{q.get('answer', '')}`") 
            
            keep_question = st.checkbox(f"Include Question {index + 1}", value=True, key=f"chk_{index}")
            if keep_question:
                approved_questions.append(q)
            st.write("---")
            
        if st.button("Publish Final Quiz to Database"):
            if not quiz_title.strip():
                st.error("⚠️ Please scroll up and enter a Quiz Title before publishing!")
            elif len(approved_questions) == 0:
                st.error("You must select at least one question!")
            else:
                try:
                    quiz_id = f"quiz_{uuid.uuid4().hex[:8]}" 

                    db.collection("quizzes").document(quiz_id).set({
                        "title": quiz_title, 
                        "difficulty": difficulty,
                        "questions": approved_questions,
                        "teacher_email": st.session_state.user_email # <--- Add this single line!
                    })
                    
                    #base_url = "http://localhost:8501" 
                    #shareable_link = f"{base_url}/?quiz={quiz_id}"
                    # Use your actual live internet URL!
                    base_url = "https://my-smart-flashcards.streamlit.app" 
                    shareable_link = f"{base_url}/?quiz={quiz_id}"
                    
                    st.success(f"'{quiz_title}' successfully generated and saved to the database!")
                    st.subheader("🔗 Your Shareable Quiz Link")
                    st.code(shareable_link, language="markdown")
                    
                    del st.session_state['draft_quiz'] 
                except Exception as e:
                    st.error(f"Database Error: {e}")
                    
    # ---------------------------------------------------------
    # STEP 4: ANALYTICS DASHBOARD
    # ---------------------------------------------------------
    st.divider()
    st.header("📊 Exam Analytics")

    if st.button("Load / Refresh Analytics Database"):
        with st.spinner("Fetching data from Firestore..."):
            try:
                # --- FIREWALL STEP 1: Find only the quizzes created by THIS teacher ---
                my_quizzes_ref = db.collection("quizzes").where("teacher_email", "==", st.session_state.user_email).stream()
                my_quiz_ids = [doc.id for doc in my_quizzes_ref]
                
                # --- FIREWALL STEP 2: Fetch scores and filter out other teachers' data ---
                scores_ref = db.collection("scores").stream()
                score_data = []
                
                for doc in scores_ref:
                    data = doc.to_dict()
                    
                    # Only add the score to the table if the quiz belongs to this teacher!
                    if data.get("quiz_id") in my_quiz_ids:
                        
                        raw_score = data.get("score", 0)
                        if raw_score <= 5: 
                            raw_score = (raw_score / 5) * 100
                            
                        score_data.append({
                            "Quiz Name": data.get("quiz_title", data.get("quiz_id", "Unknown")),
                            "Student": data.get("student_email", "Unknown"),
                            "Score (%)": raw_score
                        })
                
                st.session_state['analytics_data'] = score_data
                    
            except Exception as e:
                st.error(f"Failed to load analytics: {e}")

    if 'analytics_data' in st.session_state:
        score_data = st.session_state['analytics_data']
        
        if len(score_data) > 0:
            df = pd.DataFrame(score_data)
            unique_exams = df['Quiz Name'].unique()
            selected_exam = st.selectbox("Select an Exam to Analyze:", unique_exams)
            filtered_df = df[df['Quiz Name'] == selected_exam]
            
            if not filtered_df.empty:
                class_avg = filtered_df['Score (%)'].mean()
                st.metric(label=f"Class Average for {selected_exam}", value=f"{class_avg:.2f}%")
                
                st.write("### Student Performance Roster")
                st.dataframe(filtered_df.sort_values(by="Score (%)", ascending=False), use_container_width=True)
            else:
                st.warning("No data found for this selection.")
        else:
            st.info("No student submissions found in the database yet.")
