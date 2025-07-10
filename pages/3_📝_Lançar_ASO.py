import streamlit as st
from firebase_utils import db, bucket, log_activity, firestore # <-- CORREÇÃO AQUI
from datetime import datetime
import os

if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# st.logo("logobd.png") # Descomente se o arquivo de logo já estiver no GitHub
st.title("Lançamento de Novo ASO")

with st.form("lancamento_aso_form", clear_on_submit=True):
    st.subheader("Dados do Funcionário e Exame")
    col1, col2 = st.columns(2)
    with col1:
        nome_funcionario = st.text_input("Nome do Funcionário*", key="nome")
        funcao = st.text_input("Função", key="funcao")
        tipo_exame = st.selectbox("Tipo de Exame", ["Admissional", "Periódico", "Demissional", "Mudança de Risco", "Retorno ao Trabalho"])
        resultado = st.selectbox("Resultado", ["Apto", "Inapto", "Apto com Restrições"])
    with col2:
        data_exame = st.date_input("Data do Exame*")
        data_vencimento = st.date_input("Data de Vencimento do ASO*")
        nome_medico = st.text_input("Nome do Médico Responsável")
        crm_medico = st.text_input("CRM do Médico")

    st.subheader("Anexo do ASO")
    arquivo_aso = st.file_uploader("Selecione a foto ou PDF do ASO", type=['png', 'jpg', 'jpeg', 'pdf'])

    submit_button = st.form_submit_button(label="Salvar ASO")

if submit_button:
    if not nome_funcionario or not data_exame or not data_vencimento:
        st.warning("Por favor, preencha os campos obrigatórios (*).")
    else:
        with st.spinner("Salvando ASO..."):
            url_arquivo = None
            if arquivo_aso is not None:
                # Usa o UID do usuário para criar uma pasta única, melhorando a segurança e organização
                file_name = f"asos/{st.session_state['uid']}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{arquivo_aso.name}"
                blob = bucket.blob(file_name)
                # Faz o upload a partir dos bytes do arquivo
                blob.upload_from_string(arquivo_aso.getvalue(), content_type=arquivo_aso.type)
                blob.make_public() # Torna o arquivo publicamente acessível via URL
                url_arquivo = blob.public_url

            aso_data = {
                "nome_funcionario": nome_funcionario,
                "funcao": funcao,
                "tipo_exame": tipo_exame,
                "resultado": resultado,
                "data_exame": datetime.combine(data_exame, datetime.min.time()),
                "data_vencimento": datetime.combine(data_vencimento, datetime.min.time()),
                "nome_medico": nome_medico,
                "crm_medico": crm_medico,
                "url_arquivo_aso": url_arquivo,
                "lancado_por": st.session_state['username'],
                "data_lancamento": firestore.SERVER_TIMESTAMP # Agora 'firestore' é reconhecido
            }

            db.collection("asos").add(aso_data)
            log_activity(st.session_state['username'], "ASO Created", f"Funcionário: {nome_funcionario}")
            st.success(f"ASO para '{nome_funcionario}' lançado com sucesso!")
