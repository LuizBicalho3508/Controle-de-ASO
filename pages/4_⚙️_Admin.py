import streamlit as st
import pandas as pd
from firebase_admin import auth
from firebase_utils import log_activity

# ... (verificação de login e role admin) ...

st.title("Painel de Administração de Usuários")

with st.form("new_user_form"):
    st.subheader("Cadastrar Novo Usuário")
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    role = st.selectbox("Nível de Acesso", ["usuario", "admin"])
    
    if st.form_submit_button("Criar Usuário"):
        try:
            user = auth.create_user(email=email, password=password)
            # Definir a role como uma custom claim
            auth.set_custom_user_claims(user.uid, {'role': role})
            log_activity(st.session_state['username'], "User Created", f"New user: {email}, Role: {role}")
            st.success(f"Usuário {email} criado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao criar usuário: {e}")

st.subheader("Gerenciar Usuários")
users_list = auth.list_users().iterate_all()
users_data = []
for user in users_list:
    role = user.custom_claims.get('role', 'usuario') if user.custom_claims else 'usuario'
    users_data.append({"UID": user.uid, "Email": user.email, "Role": role})

df_users = pd.DataFrame(users_data)
st.dataframe(df_users, use_container_width=True, hide_index=True)
# A edição e exclusão aqui seguiriam um padrão similar ao do dashboard (botões por linha)
