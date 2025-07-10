import streamlit as st
import pandas as pd
from firebase_admin import auth
from firebase_utils import log_activity
from datetime import datetime

if st.session_state.get("role") != "admin":
    st.error("Acesso negado. Esta página é restrita a administradores.")
    st.stop()

st.logo("logobd.png") # ADICIONADO AQUI
st.title("Painel de Administração de Usuários")

with st.form("new_user_form", clear_on_submit=True):
    st.subheader("Cadastrar Novo Usuário")
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    role = st.selectbox("Nível de Acesso", ["usuario", "admin"])
    
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

st.subheader("Gerenciar Usuários")
try:
    users_list = auth.list_users().iterate_all()
    users_data = []
    for user in users_list:
        role = user.custom_claims.get('role', 'usuario') if user.custom_claims else 'usuario'
        last_signed_in = 'Nunca'
        if user.user_metadata and user.user_metadata.last_sign_in_timestamp:
            last_signed_in = datetime.fromtimestamp(user.user_metadata.last_sign_in_timestamp / 1000).strftime('%d/%m/%Y %H:%M')
            
        users_data.append({
            "UID": user.uid, 
            "Email": user.email, 
            "Nível": role, 
            "Logado Por Último": last_signed_in
        })
    
    df_users = pd.DataFrame(users_data)
    st.dataframe(df_users, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Erro ao carregar usuários: {e}")
