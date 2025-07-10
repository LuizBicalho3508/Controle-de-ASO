import streamlit as st
from firebase_utils import db, bucket, log_activity
from datetime import datetime
import os

if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

st.set_page_config(layout="wide")
st.logo("logobd.png")
st.title("Lançamento de Novo ASO")

with st.form("lancamento_aso_form", clear_on_submit=True):
    # ... (mesmos inputs do formulário anterior) ...
    nome_funcionario = st.text_input("Nome do Funcionário")
    # ... adicione todos os outros inputs aqui ...
    data_vencimento = st.date_input("Data de Vencimento do ASO")
    foto_aso = st.file_uploader("Selecione a foto ou PDF do ASO", type=['png', 'jpg', 'jpeg', 'pdf'])
    submit_button = st.form_submit_button(label="Salvar ASO")

if submit_button:
    if not nome_funcionario or not data_vencimento:
        st.warning("Preencha os campos obrigatórios.")
    else:
        with st.spinner("Salvando ASO..."):
            url_foto = None
            if foto_aso is not None:
                # Lógica de Upload para o Firebase Storage
                file_name = f"asos/{st.session_state['uid']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto_aso.name}"
                blob = bucket.blob(file_name)
                blob.upload_from_file(foto_aso, content_type=foto_aso.type)
                blob.make_public()
                url_foto = blob.public_url

            # Preparar dados para o Firestore
            aso_data = {
                "nome_funcionario": nome_funcionario,
                # ... todos os outros campos do formulário ...
                "data_vencimento": datetime.combine(data_vencimento, datetime.min.time()),
                "url_foto_aso": url_foto,
                "lancado_por": st.session_state['username'],
                "data_lancamento": firestore.SERVER_TIMESTAMP
            }

            # Salvar no Firestore
            db.collection("asos").add(aso_data)

            # Registrar a atividade
            log_activity(st.session_state['username'], "ASO Created", f"Funcionário: {nome_funcionario}")
            
            st.success(f"ASO para '{nome_funcionario}' lançado com sucesso!")
