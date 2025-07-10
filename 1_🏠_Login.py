import streamlit as st
import requests  # Importa a nova biblioteca
from firebase_admin import auth
from firebase_utils import log_activity # Importa apenas a função de log

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

# --- NOVA LÓGICA DE LOGIN USANDO A API REST ---
def login_user(email, password):
    # Pega a chave da API Web do arquivo de segredos
    api_key = st.secrets["firebase_config"]["apiKey"]
    
    # Monta a URL da API de autenticação do Firebase
    rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    # Prepara os dados para enviar na requisição
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        # Faz a requisição POST para a API
        response = requests.post(rest_api_url, json=payload)
        response.raise_for_status()  # Lança um erro se a resposta for de falha (4xx ou 5xx)
        
        user_data = response.json()
        uid = user_data['localId']
        
        # Após o login bem-sucedido, usa o firebase-admin para pegar as permissões (role)
        user_record = auth.get_user(uid)
        role = user_record.custom_claims.get('role', 'usuario') if user_record.custom_claims else 'usuario'

        # Atualiza o estado da sessão
        st.session_state.update({
            "authentication_status": True,
            "username": user_data['email'],
            "uid": uid,
            "role": role
        })
        log_activity(email, "Login Succeeded")
        st.rerun()

    except requests.exceptions.HTTPError as e:
        # Trata erros específicos de login (senha errada, usuário não encontrado)
        error_json = e.response.json().get("error", {})
        error_message = error_json.get("message", "ERRO_DESCONHECIDO")
        
        if "INVALID_LOGIN_CREDENTIALS" in error_message or "INVALID_PASSWORD" in error_message or "EMAIL_NOT_FOUND" in error_message:
            st.error("Email ou senha incorretos.")
        else:
            st.error(f"Erro de autenticação: {error_message}")
            
        log_activity(email, "Login Failed", error_message)
        st.session_state["authentication_status"] = False
        
    except Exception as e:
        # Trata outros erros (ex: falha de rede)
        st.error(f"Ocorreu um erro inesperado: {e}")
        log_activity(email, "Login Failed", str(e))
        st.session_state["authentication_status"] = False


# --- LÓGICA DE LOGOUT ---
def logout_user():
    if "username" in st.session_state and st.session_state["username"]:
        log_activity(st.session_state["username"], "Logout")
    st.session_state.clear()
    st.session_state["authentication_status"] = None
    st.rerun()

# --- INTERFACE (permanece a mesma) ---
st.logo("logobd.png")

if not st.session_state.get("authentication_status"):
    st.title("Sistema de Controle de ASO")
    st.subheader("Por favor, realize o login para continuar")

    with st.form("login_form"):
        email = st.text_input("Email")
        senha = st.text_input("Senha", type='password')
        login_button = st.form_submit_button("Login")

        if login_button:
            if email and senha:
                login_user(email, senha)
            else:
                st.warning("Por favor, preencha email e senha.")
else:
    st.sidebar.success(f"Bem-vindo, {st.session_state['username']}!")
    st.sidebar.write(f"Nível de Acesso: **{st.session_state['role'].upper()}**")
    st.sidebar.button("Logout", on_click=logout_user)
    
    st.header("Bem-vindo ao Sistema de Controle de ASO!")
    st.info("Utilize o menu na barra lateral esquerda para navegar entre as páginas.")
