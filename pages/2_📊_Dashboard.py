import streamlit as st
import pandas as pd
from firebase_utils import db, log_activity
from datetime import datetime

# ... (verificação de login) ...

st.set_page_config(layout="wide")
st.logo("logobd.png")
st.title("Dashboard de Controle de ASOs")

@st.cache_data(ttl=300)
def carregar_asos_firestore():
    asos_ref = db.collection("asos").stream()
    asos = [doc.to_dict() for doc in asos_ref]
    asos_com_id = []
    for doc in db.collection("asos").stream():
        aso_data = doc.to_dict()
        aso_data['id'] = doc.id
        asos_com_id.append(aso_data)
    return pd.DataFrame(asos_com_id)

df_asos = carregar_asos_firestore()

if df_asos.empty:
    st.info("Nenhum ASO cadastrado.")
    st.stop()

# --- Lógica de Alertas (mesma de antes) ---
df_asos['data_vencimento'] = pd.to_datetime(df_asos['data_vencimento'])
# ... (cálculo de 'dias_para_vencer' e 'Status') ...

# --- MELHORIA: Filtros Avançados ---
st.subheader("Filtros")
col_filter1, col_filter2 = st.columns(2)
status_filter = col_filter1.multiselect("Filtrar por Status", options=df_asos['Status'].unique(), default=df_asos['Status'].unique())
nome_filter = col_filter2.text_input("Filtrar por Nome do Funcionário")

df_filtrado = df_asos[df_asos['Status'].isin(status_filter)]
if nome_filter:
    df_filtrado = df_filtrado[df_filtrado['nome_funcionario'].str.contains(nome_filter, case=False)]

# --- MELHORIA: Botão de Exportação ---
csv = df_filtrado.to_csv(index=False).encode('utf-8')
st.download_button(
   "Exportar para CSV",
   csv,
   "relatorio_asos.csv",
   "text/csv",
   key='download-csv'
)

# --- Tabela Interativa com Edição/Exclusão ---
st.subheader("Relação de ASOs")

# Recriar o dataframe para exibição com colunas de ação
df_display = df_filtrado.copy()
df_display['Ações'] = ''

for index, row in df_display.iterrows():
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
    col1.write(row['nome_funcionario'])
    col2.write(row['data_vencimento'].strftime('%d/%m/%Y'))
    col3.write(row['Status'])
    
    # Placeholders para os botões de ação
    view_button = col4.button("👁️ Ver", key=f"view_{row['id']}")
    edit_button = col4.button("✏️ Editar", key=f"edit_{row['id']}")
    delete_button = col5.button("🗑️ Excluir", key=f"del_{row['id']}", type="primary")

    if view_button:
        # Lógica para mostrar detalhes em um expander ou dialog
        with st.expander(f"Detalhes de {row['nome_funcionario']}", expanded=True):
            st.write(row) # Mostra todos os dados
            if row['url_foto_aso']:
                st.image(row['url_foto_aso'])

    if edit_button:
        # Lógica para abrir um formulário de edição (pode ser em um st.dialog)
        st.warning("Funcionalidade de edição em desenvolvimento.")

    if delete_button:
        # Lógica de exclusão com confirmação
        st.warning(f"Tem certeza que deseja excluir o ASO de {row['nome_funcionario']}?")
        if st.button("Confirmar Exclusão", key=f"confirm_del_{row['id']}"):
            db.collection("asos").document(row['id']).delete()
            log_activity(st.session_state['username'], "ASO Deleted", f"ID: {row['id']}")
            st.rerun()
