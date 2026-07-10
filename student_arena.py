import streamlit as st
import datetime

def render_student_dashboard(db, student_email, quiz_id):
    st.header("📝 Student Arena: Exam Portal")
    
    # 1. The Welcome / Missing Link Screen
    if not quiz_id:
        st.info("👋 Welcome to the Student Portal! Please use the specific quiz link provided by your teacher to access an assignment.")
        return

    if db is None:
        st.error("⚠️ Database connection missing. Cannot load the quiz.")
        return

    # 2. Fetch the Specific Quiz from Firestore
    quiz_ref = db.collection("quizzes").document(quiz_id)
    quiz_doc = quiz_ref.get()

    if not quiz_doc.exists:
        st.error(f"❌ Quiz '{quiz_id}' not found. Please check your link to ensure it is correct.")
        return

    quiz_data = quiz_doc.to_dict()
    questions = quiz_data.get("questions", [])
    quiz_title = quiz_data.get("title", "Untitled Quiz")

    st.subheader(f"📚 Assignment: {quiz_title}")
    st.caption(f"Created by: {quiz_data.get('teacher_email')}")
    st.divider()

    # 3. ANTI-CHEAT: Check if the student has already taken it
    # We ask the database: "Find any score for THIS quiz submitted by THIS email"
    scores_query = db.collection("scores").where("quiz_id", "==", quiz_id).where("student_email", "==", student_email).get()
    
    if len(scores_query) > 0:
        # THE LOCKOUT SCREEN
        past_score_data = scores_query[0].to_dict()
        score = past_score_data.get("score")
        total = past_score_data.get("total_questions")
        
        st.success("✅ You have already completed this assignment.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Your Final Score", value=f"{score} / {total}")
        
        st.info("You may safely close this window. Your teacher has already received your grade.")
        return

    # 4. RENDER THE QUIZ (If they haven't taken it yet)
    st.write("Please answer all questions below carefully. You can only submit this quiz **once**.")
    
    # st.form packages all the answers together so it only grades when they click submit
    with st.form(key="student_quiz_form"):
        user_answers = {}
        
        for i, q in enumerate(questions):
            st.markdown(f"**Question {i+1}:** {q['question']}")
            # Using radio buttons, defaulting to None so they are forced to pick an answer
            user_answers[i] = st.radio("Select your answer:", q['options'], key=f"q_{i}", index=None)
            st.write("") # Adds a small physical space between questions

        # The big submit button at the bottom
        submit_button = st.form_submit_button(label="Submit Final Answers", type="primary")

    # 5. GRADING AND SAVING ENGINE
    if submit_button:
        # Prevent submitting if they left something blank
        if None in user_answers.values():
            st.warning("⚠️ Please answer every question before submitting.")
            return
        
        with st.spinner("Grading your exam and securely saving results..."):
            score = 0
            total_questions = len(questions)
            
            # Grade the test automatically
            for i, q in enumerate(questions):
                if user_answers[i] == q['answer']:
                    score += 1
            
            # Save the final grade to a brand new "scores" collection in Firestore
            try:
                db.collection("scores").add({
                    "quiz_id": quiz_id,
                    "quiz_title": quiz_title,
                    "student_email": student_email,
                    "teacher_email": quiz_data.get("teacher_email"),
                    "score": score,
                    "total_questions": total_questions,
                    "timestamp": datetime.datetime.now()
                })
                
                # Use st.rerun() to instantly trigger the Anti-Cheat Lockout screen above!
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to save score to the database: {e}")