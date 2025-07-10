import streamlit as st
from firebase_utils import pyrebase_auth, log_activity
from firebase_admin import auth

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Controle de ASO", page_icon="🩺", layout="wide")

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "authentication_status" not in st.session_state:
    st.session_state.update({
        "authentication_status": None,
        "username": None,
        "uid": None,
        "role": None
    })

# --- LÓGICA DE LOGIN ---
def login_user(email, password):
    try:
        user = pyrebase_auth.sign_in_with_email_and_password(email, password)
        uid = user['localId']
        
        # Obter claims customizadas (role)
        user_record = auth.get_user(uid)
        role = user_record.custom_claims.get('role', 'usuario') # Padrão é 'usuario'

        st.session_state.update({
            "authentication_status": True,
            "username": user['email'],
            "uid": uid,
            "role": role
        })
        log_activity(email, "Login Succeeded")
        st.rerun()
    except Exception as e:
        st.session_state["authentication_status"] = False
        log_activity(email, "Login Failed", str(e))
        st.error("Email ou senha incorretos.")

# --- LÓGICA DE LOGOUT ---
def logout_user():
    log_activity(st.session_state["username"], "Logout")
    st.session_state.update({
        "authentication_status": None, "username": None, "uid": None, "role": None
    })
    st.rerun()

# --- INTERFACE ---
st.logo("logobd.png")

if not st.session_state["authentication_status"]:
    st.title("Sistema de Controle de ASO")
    st.subheader("Por favor, realize o login para continuar")

    with st.form("login_form"):
        email = st.text_input("Email")
        senha = st.text_input("Senha", type='password')
        login_button = st.form_submit_button("Login")

        if login_button:
            login_user(email, senha)
else:
    st.sidebar.success(f"Bem-vindo, {st.session_state['username']}!")
    st.sidebar.write(f"Nível de Acesso: **{st.session_state['role'].upper()}**")
    st.sidebar.button("Logout", on_click=logout_user)
    
    st.header("Bem-vindo ao Sistema de Controle de ASO!")
    st.info("Utilize o menu na barra lateral esquerda para navegar entre as páginas.")
