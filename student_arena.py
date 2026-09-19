import streamlit as st
import pandas as pd

def render_student_dashboard(db, user_email, quiz_id):
    
   # ---------------------------------------------------------
    # STEP 1: STUDENT ANALYTICS DASHBOARD
    # ---------------------------------------------------------
    with st.expander("📊 View My Past Exam Grades"):
        try:
            my_scores_ref = db.collection("scores").where("student_email", "==", user_email).stream()
            my_data = []
            
            for doc in my_scores_ref:
                data = doc.to_dict()
                
                # --- THE MAGIC PATCH FOR LEGACY DATA ---
                raw_score = data.get("score", 0)
                if raw_score <= 5: 
                    raw_score = (raw_score / 5) * 100
                    
                my_data.append({
                    "Exam Name": data.get("quiz_title", data.get("quiz_id", "Unknown")),
                    "Score (%)": raw_score
                })
                
            if len(my_data) > 0:
                student_df = pd.DataFrame(my_data)
                my_avg = student_df['Score (%)'].mean()
                st.metric(label="My Overall Academic Average", value=f"{my_avg:.2f}%")
                st.dataframe(student_df, use_container_width=True)
            else:
                st.info("You haven't completed any exams yet.")
        except Exception as e:
            st.error(f"Error loading your grades: {e}")
            
    st.divider()
    st.title("Student Arena: Take Quiz")

    # ---------------------------------------------------------
    # STEP 2: LINK VALIDATION & THE VAULT DOOR
    # ---------------------------------------------------------
    if not quiz_id:
        st.warning("No quiz selected! Please use the specific shareable link provided by your teacher.")
        return
        
    # THE VAULT DOOR
    submission_id = f"{quiz_id}_{user_email}"
    existing_submission = db.collection("scores").document(submission_id).get()
    
    if existing_submission.exists:
        st.error("🔒 Access Denied: You have already completed this assessment. Multiple attempts are strictly prohibited.")
        return

    # ---------------------------------------------------------
    # STEP 3: FETCH QUIZ & DYNAMIC UI RENDER
    # ---------------------------------------------------------
    try:
        quiz_ref = db.collection("quizzes").document(quiz_id)
        quiz_doc = quiz_ref.get()
        
        if not quiz_doc.exists:
            st.error("Quiz not found! The link might be invalid or the teacher deleted it.")
            return
            
        quiz_data = quiz_doc.to_dict()
        questions = quiz_data.get("questions", [])
        difficulty = quiz_data.get("difficulty", "Standard")
        
        # --- NEW: Fetch the title and display it ---
        quiz_title = quiz_data.get("title", quiz_id) 
        
        st.write(f"**Assessment:** {quiz_title}")
        st.write(f"**Mode:** {difficulty}")
        st.divider()
        
        if 'student_answers' not in st.session_state:
            st.session_state['student_answers'] = {}
            
        for index, q in enumerate(questions):
            st.write(f"**Q{index + 1}: {q.get('question', '')}**")
            
            q_type = q.get("type", "mcq")
            options = q.get("options", [])
            answer = None
            
            if q_type in ["mcq", "tf", "spot_error"]:
                if q_type == "tf" and not options:
                    options = ["True", "False"]
                answer = st.radio(
                    "Select your answer:", 
                    options=options, 
                    key=f"ans_{index}",
                    index=None
                )
                
            elif q_type == "fib":
                answer = st.text_input("Type your answer:", key=f"ans_{index}")
                
            elif q_type == "multi_select":
                st.write("*Select ALL that apply:*")
                selected_options = []
                for opt in options:
                    if st.checkbox(opt, key=f"ans_{index}_{opt}"):
                        selected_options.append(opt)
                answer = selected_options
                
            st.session_state['student_answers'][f"Q{index+1}"] = answer
            st.write("---")
            
        # ---------------------------------------------------------
        # STEP 4: THE VALIDATION GATE & AUTO-GRADING
        # ---------------------------------------------------------
        if st.button("Submit Assessment"):
            answers_list = list(st.session_state['student_answers'].values())
            
            if any(a is None or a == "" or a == [] for a in answers_list):
                st.error("⚠️ Validation Error: You must attempt every single question before submitting!")
            else:
                with st.spinner("Auto-grading your assessment..."):
                    correct_count = 0
                    total_questions = len(questions)

                    # THE AUTO-GRADER
                    for index, q in enumerate(questions):
                        student_ans = st.session_state['student_answers'][f"Q{index+1}"]
                        correct_ans = q.get("answer")
                        
                        if q.get("type") == "multi_select":
                            if isinstance(correct_ans, list) and isinstance(student_ans, list):
                                # Clean both lists to prevent spacing/capitalization mismatches
                                clean_student = set([str(x).strip().lower() for x in student_ans])
                                clean_correct = set([str(x).strip().lower() for x in correct_ans])
                                if clean_student == clean_correct:
                                    correct_count += 1
                        else:
                            clean_student = str(student_ans).strip().lower()
                            clean_correct = str(correct_ans).strip().lower()
                            
                            # Safety net: Check for exact match OR if Gemini accidentally gave a single letter
                            if clean_student == clean_correct:
                                correct_count += 1
                            elif len(clean_correct) == 1 and clean_student.startswith(clean_correct):
                                correct_count += 1
                                
                    # Calculate final percentage
                    if total_questions > 0:
                        final_score = (correct_count / total_questions) * 100
                    else:
                        final_score = 0
                        
                    submission_data = {
                        "student_email": user_email,
                        "quiz_id": quiz_id,
                        "quiz_title": quiz_title, 
                        "answers": st.session_state['student_answers'],
                        "score": final_score
                    }
                    
                    # Save to database
                    db.collection("scores").document(submission_id).set(submission_data)
                    
                    # Tell the student exactly how many they got right!
                    st.success(f"Assessment submitted! You got {correct_count} out of {total_questions} correct ({final_score:.2f}%).")
                    del st.session_state['student_answers']
                    
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Error loading quiz: {e}")
