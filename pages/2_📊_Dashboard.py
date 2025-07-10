import streamlit as st
import pandas as pd
from firebase_utils import db, log_activity, firestore
from datetime import datetime, timezone

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Configurações da Página ---
# st.logo("logobd.png")
st.title("Dashboard de Controle de ASOs")

# --- Função para carregar os dados ---
@st.cache_data(ttl=60)
def carregar_asos_firestore():
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
hoje = datetime.now(timezone.utc)
df_asos['dias_para_vencer'] = (df_asos['data_vencimento'] - hoje).dt.days

def definir_status(dias):
    if dias < 0: return "Vencido"
    elif dias <= 30: return "Vence em até 30 dias"
    elif dias <= 60: return "Vence em até 60 dias"
    else: return "Em dia"
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

df_filtrado = df_asos[df_asos['Status'].isin(status_filter)]
if nome_filter:
    df_filtrado = df_filtrado[df_filtrado['nome_funcionario'].str.contains(nome_filter, case=False, na=False)]

# --- Tabela de ASOs ---
df_display = df_filtrado[['nome_funcionario', 'funcao', 'data_vencimento', 'Status', 'id']].copy()
df_display['data_vencimento'] = df_display['data_vencimento'].dt.strftime('%d/%m/%Y')

# Inicializa o estado para o expander
if 'expanded_aso' not in st.session_state:
    st.session_state.expanded_aso = None

for index, row in df_display.iterrows():
    container = st.container(border=True)
    with container:
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        col1.write(f"**{row['nome_funcionario']}** ({row.get('funcao', 'N/A')})")
        col2.write(f"Vence em: {row['data_vencimento']}")
        col3.markdown(f"Status: **{row['Status']}**")

        if col4.button("👁️ Ver Detalhes", key=f"view_{row['id']}"):
            # Se o botão clicado for o já expandido, fecha ele. Senão, abre o novo.
            if st.session_state.expanded_aso == row['id']:
                st.session_state.expanded_aso = None
            else:
                st.session_state.expanded_aso = row['id']
            st.rerun()

        # Lógica de exclusão (pode ser movida para dentro do expander se preferir)
        if st.session_state.get("role") == "admin":
            if col4.button("🗑️ Excluir", key=f"del_{row['id']}", type="primary"):
                st.session_state.delete_aso_id = row['id']
                st.rerun()

    # --- LÓGICA DE VISUALIZAÇÃO COM EXPANDER ---
    if st.session_state.expanded_aso == row['id']:
        with container: # Continua dentro do mesmo container para manter o layout
            with st.expander("Detalhes do ASO", expanded=True):
                doc = db.collection('asos').document(row['id']).get()
                if doc.exists:
                    details = doc.to_dict()
                    for key, value in details.items():
                        if 'data' in key and isinstance(value, datetime):
                            st.write(f"**{key.replace('_', ' ').title()}:** {value.strftime('%d/%m/%Y')}")
                        elif 'url' in key and value:
                            st.link_button("Ver/Baixar Anexo", value)
                        else:
                            st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                else:
                    st.warning("Não foi possível carregar os detalhes.")

# --- Lógica para o Modal de Exclusão (usando st.dialog, que é mais apropriado para confirmações) ---
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
