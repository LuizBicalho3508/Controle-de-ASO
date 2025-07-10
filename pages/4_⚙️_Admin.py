import streamlit as st
import pandas as pd
from firebase_admin import auth
from firebase_utils import log_activity
from datetime import datetime

# --- Verificação de Login e Nível de Acesso ---
if st.session_state.get("role") != "admin":
    st.error("Acesso negado. Esta página é restrita a administradores.")
    st.stop()

# --- Inicialização do Session State para Ações ---
if 'change_password_uid' not in st.session_state:
    st.session_state.change_password_uid = None

# --- Configurações da Página ---
st.logo("logobd.png")
st.title("Painel de Administração de Usuários")

# --- Formulário para Criar Novo Usuário ---
with st.expander("➕ Cadastrar Novo Usuário"):
    with st.form("new_user_form", clear_on_submit=True):
        email = st.text_input("Email")
        password = st.text_input("Senha", type="password")
        role = st.selectbox("Nível de Acesso", ["usuario", "admin"], key="new_user_role")
        
        if st.form_submit_button("Criar Usuário"):
            if email and password:
                try:
                    user = auth.create_user(email=email, password=password)
                    auth.set_custom_user_claims(user.uid, {'role': role})
                    log_activity(st.session_state['username'], "User Created", f"New user: {email}, Role: {role}")
                    st.success(f"Usuário {email} criado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao criar usuário: {e}")
            else:
                st.warning("Preencha todos os campos.")

st.divider()
st.subheader("Gerenciar Usuários Existentes")

# --- Função para Carregar Usuários com Cache ---
@st.cache_data(ttl=60)
def carregar_usuarios():
    users_list = auth.list_users().iterate_all()
    users_data = []
    for user in users_list:
        role = user.custom_claims.get('role', 'usuario') if user.custom_claims else 'usuario'
        last_signed_in = 'Nunca'
        if user.user_metadata and user.user_metadata.last_sign_in_timestamp:
            last_signed_in = datetime.fromtimestamp(user.user_metadata.last_sign_in_timestamp / 1000).strftime('%d/%m/%Y %H:%M')
            
        users_data.append({
            "uid": user.uid, 
            "email": user.email, 
            "role": role, 
            "disabled": user.disabled,
            "last_sign_in": last_signed_in
        })
    return users_data

try:
    usuarios = carregar_usuarios()
    
    # --- Loop Interativo para Gerenciar Usuários ---
    for user in usuarios:
        if user['uid'] == st.session_state.get('uid'):
            continue

        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            
            status_text = "🔴 Desabilitado" if user['disabled'] else "🟢 Habilitado"
            col1.write(f"**Email:** {user['email']}")
            col1.write(f"**Nível:** {user['role'].capitalize()}")
            col1.write(f"**Status:** {status_text}")

            # Ações de Habilitar/Desabilitar
            if user['disabled']:
                if col2.button("✅ Habilitar Usuário", key=f"enable_{user['uid']}"):
                    auth.update_user(user['uid'], disabled=False)
                    log_activity(st.session_state['username'], "User Enabled", f"User: {user['email']}")
                    st.success(f"Usuário {user['email']} habilitado.")
                    carregar_usuarios.clear() # <- CORREÇÃO: Limpa o cache
                    st.rerun()
            else:
                if col2.button("🚫 Desabilitar Usuário", key=f"disable_{user['uid']}", type="primary"):
                    auth.update_user(user['uid'], disabled=True)
                    log_activity(st.session_state['username'], "User Disabled", f"User: {user['email']}")
                    st.warning(f"Usuário {user['email']} desabilitado.")
                    carregar_usuarios.clear() # <- CORREÇÃO: Limpa o cache
                    st.rerun()

            # Ações de Senha
            if col3.button("🔑 Alterar Senha", key=f"pwd_{user['uid']}"):
                st.session_state.change_password_uid = user['uid'] if st.session_state.change_password_uid != user['uid'] else None
                st.rerun()

            if st.session_state.change_password_uid == user['uid']:
                with st.form(f"form_pwd_{user['uid']}", clear_on_submit=True):
                    new_password = st.text_input("Nova Senha", type="password", key=f"new_pwd_input_{user['uid']}")
                    if st.form_submit_button("Confirmar Nova Senha"):
                        if len(new_password) >= 6:
                            auth.update_user(user['uid'], password=new_password)
                            log_activity(st.session_state['username'], "Password Changed", f"For user: {user['email']}")
                            st.success(f"Senha do usuário {user['email']} alterada com sucesso!")
                            st.session_state.change_password_uid = None
                            st.rerun()
                        else:
                            st.error("A nova senha deve ter no mínimo 6 caracteres.")

except Exception as e:
    st.error(f"Erro ao carregar ou gerenciar usuários: {e}")
