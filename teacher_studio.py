import streamlit as st
import io
import uuid
import json
import pypdf
import docx
import google.generativeai as genai

# --- 1. DOCUMENT PARSERS ---
def parse_pdf(file_bytes):
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
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
        doc = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        st.error(f"Error parsing Word Document: {e}")
        return ""

# --- 2. AI GENERATOR ENGINE ---
def generate_quiz_with_ai(text, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        You are an expert tutor. Analyze the following text. 
        Extract exactly 5 meaningful, highly accurate multiple-choice questions based strictly on the text.
        
        Style Requirement:
        Every question must have a 'question' text, an 'answer' text (the correct answer), and an 'options' array containing exactly 4 choices (including the correct answer).
        
        You MUST respond ONLY with a valid JSON array of objects. Do not add markdown blocks like ```json.
        Each object must match this structure exactly:
        {{"question": "What is X?", "answer": "The correct answer", "options": ["Wrong 1", "The correct answer", "Wrong 2", "Wrong 3"]}}
        
        Text to analyze:
        {text}
        """
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"} 
        )
        
        quiz_data = json.loads(response.text)
        return quiz_data, None
        
    except Exception as e:
        return None, str(e)

# --- 3. THE TEACHER DASHBOARD UI ---
def render_teacher_dashboard(db, api_key):
    st.header("🎓 Teacher Studio: Quiz Generator")
    st.markdown("Upload course material to instantly generate and share AI-powered quizzes.")
    
    if not api_key:
        st.error("⚠️ Gemini API Key is missing. Please check your configuration.")
        return
        
    if db is None:
        st.error("⚠️ Database connection missing. Cannot save quizzes.")
        return

    # Upload Section
    quiz_title = st.text_input("Enter a Title for this Quiz (e.g., Biology Chapter 1):")
    uploaded_file = st.file_uploader("Upload a study document (PDF or DOCX)", type=['pdf', 'docx'])
    
    if st.button("Generate & Save Quiz", type="primary"):
        if not quiz_title:
            st.warning("Please provide a title for the quiz.")
        elif not uploaded_file:
            st.warning("Please upload a document to analyze.")
        else:
            with st.spinner("Extracting text and generating questions with AI..."):
                # 1. Read the file
                file_bytes = uploaded_file.read()
                if uploaded_file.name.endswith('.pdf'):
                    raw_text = parse_pdf(file_bytes)
                else:
                    raw_text = parse_docx(file_bytes)
                
                # 2. Call the AI
                if len(raw_text.strip()) < 50:
                    st.error("Not enough text found in the document to generate a quiz.")
                    return
                    
                quiz_data, error = generate_quiz_with_ai(raw_text, api_key)
                
                if error:
                    st.error(f"AI Generation Failed: {error}")
                elif quiz_data:
                    # 3. Save to Database
                    quiz_id = f"quiz_{uuid.uuid4().hex[:8]}" # Generates a unique short code
                    teacher_email = st.session_state.user_email
                    
                    try:
                        db.collection("quizzes").document(quiz_id).set({
                            "title": quiz_title,
                            "teacher_email": teacher_email,
                            "questions": quiz_data,
                            "active": True
                        })
                        
                        st.success("✅ Quiz successfully generated and saved to the database!")
                        
                        # 4. Generate the Shareable Link
                        st.divider()
                        st.subheader("🔗 Your Shareable Quiz Link")
                        st.markdown("Copy the link below and share it with your students:")
                        
                        # Adjust this base URL to match your Streamlit Cloud URL
                        base_url = "https://my-smart-flashcards.streamlit.app/"
                        share_link = f"{base_url}?quiz={quiz_id}"
                        
                        st.code(share_link, language="text")
                        
                        # Preview the generated questions
                        with st.expander("Preview Generated Questions"):
                            for idx, q in enumerate(quiz_data):
                                st.write(f"**Q{idx+1}: {q['question']}**")
                                st.write(f"Options: {', '.join(q['options'])}")
                                st.write(f"Answer: ✅ {q['answer']}")
                                
                    except Exception as db_error:
                        st.error(f"Failed to save to database: {db_error}")