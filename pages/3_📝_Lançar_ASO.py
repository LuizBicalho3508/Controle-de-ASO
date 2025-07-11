import streamlit as st
from firebase_utils import db, bucket, log_activity, firestore
from datetime import datetime

if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

st.logo("logobd.png")
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

    st.subheader("Anexos (ASO, Exames Complementares, etc.)")
    # MUDANÇA: aceita múltiplos arquivos
    arquivos_aso = st.file_uploader(
        "Selecione um ou mais arquivos",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        accept_multiple_files=True
    )

    submit_button = st.form_submit_button(label="Salvar ASO")

if submit_button:
    if not nome_funcionario or not data_exame or not data_vencimento:
        st.warning("Por favor, preencha os campos obrigatórios (*).")
    else:
        with st.spinner("Salvando ASO e anexos..."):
            urls_anexos = []
            if arquivos_aso:
                # MUDANÇA: Loop para fazer upload de cada arquivo
                for arquivo in arquivos_aso:
                    file_name = f"asos/{st.session_state['uid']}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{arquivo.name}"
                    blob = bucket.blob(file_name)
                    blob.upload_from_string(arquivo.getvalue(), content_type=arquivo.type)
                    blob.make_public()
                    urls_anexos.append(blob.public_url)

            aso_data = {
                "nome_funcionario": nome_funcionario,
                "funcao": funcao,
                "tipo_exame": tipo_exame,
                "resultado": resultado,
                "data_exame": datetime.combine(data_exame, datetime.min.time()),
                "data_vencimento": datetime.combine(data_vencimento, datetime.min.time()),
                "nome_medico": nome_medico,
                "crm_medico": crm_medico,
                "anexos": urls_anexos, # MUDANÇA: Salva uma lista de URLs
                "lancado_por": st.session_state['username'],
                "data_lancamento": firestore.SERVER_TIMESTAMP
            }

            db.collection("asos").add(aso_data)
            log_activity(st.session_state['username'], "ASO Created", f"Funcionário: {nome_funcionario}")
            st.success(f"ASO para '{nome_funcionario}' lançado com sucesso!")
