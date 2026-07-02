import streamlit as st
import re
import random

# Page setup with a wide layout for a dashboard feel
st.set_page_config(page_title="FlashMind Pro", page_icon="🧠", layout="centered")

# --- Custom Quizlet-Style CSS ---
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
    }
    </style>
""", unsafe_allow_html=True)

st.title("🧠 FlashMind Pro")
st.caption("The ultimate smart-parsing study suite inspired by Quizlet.")

# --- STEP 1: Initialize Advanced Session States ---
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

# --- STEP 2: Text Parsing Rules ---
def generate_cards(text):
    cards = []
    sentences = re.split(r'(?<=[.?!])\s+|\n+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue
            
        # Parse definition style
        if " - " in sentence:
            parts = sentence.split(" - ", 1)
            cards.append({"question": f"What is the definition of: **{parts[0]}**?", "answer": parts[1].strip()})
        elif ":" in sentence:
            parts = sentence.split(":", 1)
            cards.append({"question": f"What is the concept behind: **{parts[0]}**?", "answer": parts[1].strip()})
        # Parse sentence fill-in-the-blanks
        else:
            words = sentence.split()
            clean_words = [re.sub(r'[^\w]', '', w) for w in words]
            candidate_indices = [i for i, w in enumerate(clean_words) if len(w) > 5]
            
            if candidate_indices:
                blank_idx = random.choice(candidate_indices)
                answer = clean_words[blank_idx]
                question_words = words.copy()
                question_words[blank_idx] = "________"
                cards.append({"question": "Fill in the blank:\n\n" + " ".join(question_words), "answer": answer})
                
    return cards

# --- STEP 3: Generate/Input Section ---
with st.expander("📥 Paste New Study Material", expanded=not bool(st.session_state.cards)):
    text_input = st.text_area(
        "Paste your lecture notes, glossary, or essays:", 
        height=150,
        placeholder="Example:\nDNA: The molecule that carries genetic instructions.\nPhotosynthesis: The process plants use to synthesis nutrients from sunlight."
    )
    if st.button("✨ Build Study Set", type="primary", use_container_width=True):
        if text_input.strip():
            generated = generate_cards(text_input)
            if len(generated) >= 2:
                st.session_state.cards = generated
                st.session_state.current_index = 0
                st.session_state.flipped = False
                st.session_state.quiz_score = 0
                st.session_state.quiz_answered = False
                st.session_state.quiz_options = []
                st.rerun()
            else:
                st.warning("Please provide at least 2 clear concepts or sentences so Quiz Mode has enough context options!")
        else:
            st.error("Text area cannot be blank.")

# --- STEP 4: Mode Selection Dashboard ---
if st.session_state.cards:
    total_cards = len(st.session_state.cards)
    
    # Mode selector tabs
    study_mode = st.radio("Choose Study Mode:", ["📇 Flashcards", "📝 Multiple Choice Quiz"], horizontal=True)
    st.divider()

    # Shared Progress Header
    progress_percentage = (st.session_state.current_index + 1) / total_cards
    st.progress(progress_percentage)
    st.write(f"**Progress:** Card {st.session_state.current_index + 1} of {total_cards}")

    # --- MODE A: FLASHCARDS ---
    if study_mode == "📇 Flashcards":
        current_card = st.session_state.cards[st.session_state.current_index]
        
        # Display customized flashcard wrapper
        if not st.session_state.flipped:
            st.markdown(f'<div class="flashcard-box"><p class="card-text">❓ {current_card["question"]}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="flashcard-box" style="background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);"><p class="card-text">💡 {current_card["answer"]}</p></div>', unsafe_allow_html=True)

        # Controls Layout
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Back", disabled=(st.session_state.current_index == 0), use_container_width=True):
                st.session_state.current_index -= 1
                st.session_state.flipped = False
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
                st.rerun()

    # --- MODE B: MULTIPLE CHOICE QUIZ ---
    elif study_mode == "📝 Multiple Choice Quiz":
        current_card = st.session_state.cards[st.session_state.current_index]
        correct_ans = current_card["answer"]
        
        # Generate options (distractors) only once per unique card index
        if not st.session_state.quiz_options or st.session_state.flipped: 
            # (Using st.session_state.flipped temporarily to track if we need options updated on card switch)
            all_answers = list(set([c["answer"] for c in st.session_state.cards]))
            wrong_answers = [ans for ans in all_answers if ans != correct_ans]
            
            # Select up to 3 random wrong answers
            num_distractors = min(3, len(wrong_answers))
            sampled_distractors = random.sample(wrong_answers, num_distractors)
            
            options = sampled_distractors + [correct_ans]
            random.shuffle(options)
            st.session_state.quiz_options = options
            st.session_state.flipped = False # reuse variable safely

        # Quiz Question Window
        st.markdown(f'<div class="flashcard-box"><p class="card-text">{current_card["question"]}</p></div>', unsafe_allow_html=True)
        
        # Display multiple choice options
        user_choice = st.radio("Select the correct answer:", st.session_state.quiz_options, index=None, key=f"q_{st.session_state.current_index}")
        
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
                
        # Show immediate answer breakdown feedback
        if st.session_state.quiz_answered:
            if user_choice == correct_ans:
                st.success(f"🎯 **Correct!** The answer is indeed: {correct_ans}")
            else:
                st.error(f"😢 **Incorrect.** You selected '{user_choice}'. The right answer was: **{correct_ans}**")
                
        # Sticky score metric display
        st.metric(label="Current Score", value=f"{st.session_state.quiz_score} / {total_cards}")
        
        # Reset Quiz Button
        if st.session_state.current_index == total_cards - 1 and st.session_state.quiz_answered:
            st.balloons()
            if st.button("🔄 Restart Quiz", use_container_width=True):
                st.session_state.current_index = 0
                st.session_state.quiz_score = 0
                st.session_state.quiz_answered = False
                st.session_state.quiz_options = []
                st.rerun()