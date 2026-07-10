import streamlit as st
import json
import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Smart-Parsing Study", page_icon="🧠", layout="wide")

# --- 1. MEMORY VAULT ---
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# --- 2. HYBRID SECRETS ENGINE ---
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
    except Exception:
        pass
else:
    try:
        if "secure_api_key" in st.secrets:
            api_from_config = st.secrets["secure_api_key"]
        if "firebase_web_api_key" in st.secrets:
            web_api_from_config = st.secrets["firebase_web_api_key"]
        if "firebase_service_account" in st.secrets:
            service_account_from_config = dict(st.secrets["firebase_service_account"])
            if "private_key" in service_account_from_config:
                service_account_from_config["private_key"] = service_account_from_config["private_key"].replace("\\n", "\n")
    except Exception:
        pass

# --- 3. DATABASE IGNITION ---
db = None
if service_account_from_config:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_from_config)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        st.sidebar.error(f"Database Error: {e}")

# Variables for modules to use
active_api_key = api_from_config
active_web_key = web_api_from_config

# --- 4. AUTHENTICATION LOGIC ---
def authenticate_user(email, password, mode, role=None):
    if not active_web_key:
        return {"error": "Missing Firebase Web Key"}
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:{mode}?key={active_web_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    
    try:
        response = requests.post(url, json=payload).json()
        if "error" in response:
            return {"error": response["error"]["message"]}
        
        # If signing up, save their role to the database
        if mode == "signUp" and db is not None:
            db.collection("users").document(email).set({"role": role})
            return {"success": True, "role": role}
        
        # If logging in, fetch their role from the database
        if mode == "signInWithPassword" and db is not None:
            user_doc = db.collection("users").document(email).get()
            if user_doc.exists:
                fetched_role = user_doc.to_dict().get("role", "Student")
                return {"success": True, "role": fetched_role}
            else:
                return {"success": True, "role": "Student"} # Fallback
                
    except Exception as e:
        return {"error": str(e)}

# --- 5. UI ROUTER & GATEWAY ---
if st.session_state.user_email is None:
    st.title("🧠 SMART-PARSING EDU-PLATFORM")
    st.markdown("Sign in to access your portal.")
    
    # URL Checker (Did they click a quiz link?)
    quiz_id_in_url = st.query_params.get("quiz")
    if quiz_id_in_url:
        st.info(f"🔗 You are attempting to access Quiz ID: **{quiz_id_in_url}**. Please log in as a Student to continue.")

    action = st.radio("Action", ["Log In", "Create Account"], horizontal=True)
    
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    
    role_selection = None
    if action == "Create Account":
        role_selection = st.selectbox("Register as:", ["Student", "Teacher"])
        
    if st.button("Authenticate"):
        if email and len(password) >= 6:
            mode = "signInWithPassword" if action == "Log In" else "signUp"
            result = authenticate_user(email, password, mode, role_selection)
            
            if "error" in result:
                st.error(f"Authentication Failed: {result['error']}")
            else:
                st.session_state.user_email = email
                st.session_state.user_role = result["role"]
                st.rerun()
        else:
            st.warning("Please provide a valid email and a 6+ character password.")

# --- 6. SECURE MODULAR ROUTING ---
else:
    # Top Navigation Bar
    col1, col2 = st.columns([8, 2])
    with col1:
        st.write(f"👤 Logged in as: **{st.session_state.user_email}** ({st.session_state.user_role})")
    with col2:
        if st.button("Logout", use_container_width=True):
            st.session_state.user_email = None
            st.session_state.user_role = None
            st.rerun()
            
    st.divider()

    # The Bouncer: Direct the user to the correct file
    if st.session_state.user_role == "Teacher":
        import teacher_studio
        teacher_studio.render_teacher_dashboard(db, active_api_key)
        
    elif st.session_state.user_role == "Student":
        import student_arena
        # Pass the unique URL link if it exists
        current_quiz_link = st.query_params.get("quiz")
        student_arena.render_student_dashboard(db, st.session_state.user_email, current_quiz_link)
