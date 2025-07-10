import streamlit as st
import pandas as pd
from firebase_utils import db, log_activity, firestore
from datetime import datetime, timezone # <-- MUDANÇA 1: Importa timezone

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Configurações da Página ---
# st.logo("logobd.png") # Descomente quando o logo estiver funcionando
st.title("Dashboard de Controle de ASOs")

# --- Função para carregar os dados ---
@st.cache_data(ttl=60)
def carregar_asos_firestore():
    """Carrega todos os documentos da coleção 'asos' e adiciona o ID do documento."""
    docs = db.collection("asos").stream()
    asos = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        asos.append(data)
    if not asos:
        return pd.DataFrame()
    return pd.DataFrame(asos)

# Carrega os dados
df_asos = carregar_asos_firestore()

# --- LÓGICA REESTRUTURADA ---
if df_asos.empty:
    st.info("Nenhum ASO cadastrado ainda. Vá para a página 'Lançar ASO' para adicionar o primeiro.")
    st.stop()

# --- Lógica de Alertas e Status ---
df_asos['data_vencimento'] = pd.to_datetime(df_asos['data_vencimento'])
hoje = datetime.now(timezone.utc) # <-- MUDANÇA 2: Usa a hora atual em UTC
df_asos['dias_para_vencer'] = (df_asos['data_vencimento'] - hoje).dt.days

def definir_status(dias):
    if dias < 0:
        return "Vencido"
    elif dias <= 30:
        return "Vence em até 30 dias"
    elif dias <= 60:
        return "Vence em até 60 dias"
    else:
        return "Em dia"

df_asos['Status'] = df_asos['dias_para_vencer'].apply(definir_status)

# --- Exibição dos Alertas ---
st.subheader("Alertas Importantes")
col_metric1, col_metric2, col_metric3 = st.columns(3)
vencidos = df_asos[df_asos['Status'] == 'Vencido'].shape[0]
ate_30_dias = df_asos[df_asos['Status'] == 'Vence em até 30 dias'].shape[0]
ate_60_dias = df_asos[df_asos['Status'] == 'Vence em até 60 dias'].shape[0]
col_metric1.metric("ASOs Vencidos", vencidos)
col_metric2.metric("Vencem em até 30 dias", ate_30_dias)
col_metric3.metric("Vencem em até 60 dias", ate_60_dias)

# --- Filtros Avançados ---
st.divider()
st.subheader("Filtros e Relação de ASOs")
col_filter1, col_filter2 = st.columns(2)
status_options = df_asos['Status'].unique()
status_filter = col_filter1.multiselect("Filtrar por Status", options=status_options, default=status_options)
nome_filter = col_filter2.text_input("Filtrar por Nome do Funcionário")

# Aplica os filtros
df_filtrado = df_asos[df_asos['Status'].isin(status_filter)]
if nome_filter:
    df_filtrado = df_filtrado[df_filtrado['nome_funcionario'].str.contains(nome_filter, case=False, na=False)]

# --- Tabela de ASOs ---
df_display = df_filtrado[['nome_funcionario', 'funcao', 'data_vencimento', 'Status', 'id']].copy()
df_display['data_vencimento'] = df_display['data_vencimento'].dt.strftime('%d/%m/%Y')

for index, row in df_display.iterrows():
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        col1.write(f"**{row['nome_funcionario']}** ({row.get('funcao', 'N/A')})")
        col2.write(f"Vence em: {row['data_vencimento']}")
        col3.markdown(f"Status: **{row['Status']}**")

        with col4.expander("Ações"):
            if st.button("👁️ Ver Detalhes", key=f"view_{row['id']}"):
                st.session_state.view_aso_id = row['id']
            if st.session_state.get("role") == "admin":
                if st.button("🗑️ Excluir", key=f"del_{row['id']}", type="primary"):
                    st.session_state.delete_aso_id = row['id']

# --- Lógica para os Modais de Ação ---
if 'view_aso_id' in st.session_state and st.session_state.view_aso_id:
    aso_id = st.session_state.view_aso_id
    doc = db.collection('asos').document(aso_id).get()
    if doc.exists:
        details = doc.to_dict()
        with st.dialog("Detalhes do ASO"):
            st.subheader(f"ASO de {details.get('nome_funcionario')}")
            for key, value in details.items():
                if 'data' in key and isinstance(value, datetime):
                    st.write(f"**{key.replace('_', ' ').title()}:** {value.strftime('%d/%m/%Y')}")
                elif 'url' in key and value:
                    st.link_button("Ver/Baixar Anexo", value)
                else:
                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")
            if st.button("Fechar", key="close_view"):
                del st.session_state.view_aso_id
                st.rerun()

if 'delete_aso_id' in st.session_state and st.session_state.delete_aso_id:
    aso_id_to_delete = st.session_state.delete_aso_id
    doc_ref = db.collection('asos').document(aso_id_to_delete)
    aso_name = doc_ref.get().to_dict().get('nome_funcionario', 'Desconhecido')
    with st.dialog("Confirmar Exclusão"):
        st.error(f"Tem certeza que deseja excluir o ASO de {aso_name}?")
        col1, col2 = st.columns(2)
        if col1.button("Confirmar", type="primary"):
            doc_ref.delete()
            log_activity(st.session_state['username'], "ASO Deleted", f"ID: {aso_id_to_delete}")
            del st.session_state.delete_aso_id
            st.rerun()
        if col2.button("Cancelar"):
            del st.session_state.delete_aso_id
            st.rerun()
