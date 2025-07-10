import streamlit as st
import pandas as pd
from firebase_utils import db, log_activity, firestore
from datetime import datetime, timezone

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Inicialização do Session State ---
if 'expanded_aso' not in st.session_state:
    st.session_state.expanded_aso = None
if 'delete_confirmation' not in st.session_state:
    st.session_state.delete_confirmation = None

# --- Configurações da Página ---
st.logo("logobd.png")
st.title("Dashboard de Controle de ASOs")

# --- Função para carregar os dados ---
@st.cache_data(ttl=60)
def carregar_asos_firestore():
    docs = db.collection("asos").stream()
    asos = []
    for doc in db.collection("asos").stream():
        data = doc.to_dict()
        data['id'] = doc.id
        asos.append(data)
    if not asos:
        return pd.DataFrame()
    return pd.DataFrame(asos)

# Carrega os dados
df_asos = carregar_asos_firestore()

# --- LÓGICA PRINCIPAL ---
if df_asos.empty:
    st.info("Nenhum ASO cadastrado ainda. Vá para a página 'Lançar ASO' para adicionar o primeiro.")
    st.stop()

# --- Processamento de Dados ---
df_asos['data_vencimento'] = pd.to_datetime(df_asos['data_vencimento'])
hoje = datetime.now(timezone.utc)
df_asos['dias_para_vencer'] = (df_asos['data_vencimento'] - hoje).dt.days

def definir_status(row):
    if row.get('tipo_exame') == 'Demissional':
        return 'Arquivado'
    else:
        dias = row['dias_para_vencer']
        if dias < 0: return "Vencido"
        elif dias <= 30: return "Vence em até 30 dias"
        elif dias <= 60: return "Vence em até 60 dias"
        else: return "Em dia"
df_asos['Status'] = df_asos.apply(definir_status, axis=1)

# --- Exibição dos Alertas ---
st.subheader("Alertas Importantes")
col_metric1, col_metric2, col_metric3 = st.columns(3)
vencidos = df_asos[df_asos['Status'] == 'Vencido'].shape[0]
ate_30_dias = df_asos[df_asos['Status'] == 'Vence em até 30 dias'].shape[0]
ate_60_dias = df_asos[df_asos['Status'] == 'Vence em até 60 dias'].shape[0]
col_metric1.metric("ASOs Vencidos", vencidos)
col_metric2.metric("Vencem em até 30 dias", ate_30_dias)
col_metric3.metric("Vencem em até 60 dias", ate_60_dias)

# --- GRÁFICO DE VENCIMENTOS POR MÊS ---
st.divider()
st.subheader(f"Gráfico de Vencimentos por Mês ({datetime.now().year})")

df_chart = df_asos[df_asos['Status'].isin(['Vencido', 'Vence em até 30 dias', 'Vence em até 60 dias'])].copy()
current_year = datetime.now().year
df_chart = df_chart[df_chart['data_vencimento'].dt.year == current_year]

if df_chart.empty:
    st.info(f"Nenhum ASO vencido ou próximo do vencimento para o ano de {current_year}.")
else:
    df_chart['mes_vencimento'] = df_chart['data_vencimento'].dt.month
    vencimentos_por_mes = df_chart.groupby('mes_vencimento').size().reset_index(name='Quantidade')

    meses_pt = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }
    df_grafico = pd.DataFrame({'mes_vencimento': range(1, 13)})
    df_grafico = pd.merge(df_grafico, vencimentos_por_mes, on='mes_vencimento', how='left').fillna(0)
    df_grafico['Mês'] = df_grafico['mes_vencimento'].map(meses_pt)

    # --- CORREÇÃO FINAL E DEFINITIVA ---
    # 1. Criamos uma lista com a ordem cronológica exata dos meses.
    ordem_meses_cronologica = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    
    # 2. Convertemos a coluna 'Mês' para um tipo Categórico Ordenado, usando nossa lista.
    #    Isso "ensina" ao Pandas e ao Streamlit a ordem correta.
    df_grafico['Mês'] = pd.Categorical(df_grafico['Mês'], categories=ordem_meses_cronologica, ordered=True)
    
    # 3. Ordenamos o DataFrame por esta nova categoria para garantir.
    df_grafico = df_grafico.sort_values('Mês')

    # 4. Plotamos o gráfico, que agora respeitará a ordem da categoria definida.
    st.bar_chart(df_grafico.set_index('Mês')[['Quantidade']])


# --- Filtros e Tabela ---
st.divider()
st.subheader("Filtros e Relação de ASOs")
col_filter1, col_filter2 = st.columns(2)
status_options = df_asos['Status'].unique()
status_filter = col_filter1.multiselect("Filtrar por Status", options=status_options, default=status_options)
nome_filter = col_filter2.text_input("Filtrar por Nome do Funcionário")

df_filtrado = df_asos[df_asos['Status'].isin(status_filter)]
if nome_filter:
    df_filtrado = df_filtrado[df_filtrado['nome_funcionario'].str.contains(nome_filter, case=False, na=False)]

df_display = df_filtrado[['nome_funcionario', 'funcao', 'data_vencimento', 'Status', 'id']].copy()
df_display['data_vencimento'] = df_display['data_vencimento'].dt.strftime('%d/%m/%Y')

# --- Loop de Exibição com a Lógica de Ações ---
for index, row in df_display.iterrows():
    container = st.container(border=True)
    with container:
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        col1.write(f"**{row['nome_funcionario']}** ({row.get('funcao', 'N/A')})")
        col2.write(f"Vence em: {row['data_vencimento']}")
        col3.markdown(f"Status: **{row['Status']}**")

        if col4.button("👁️ Ver Detalhes", key=f"view_{row['id']}"):
            st.session_state.expanded_aso = row['id'] if st.session_state.expanded_aso != row['id'] else None
            st.rerun()

        if st.session_state.get("role") == "admin":
            if col4.button("🗑️ Excluir", key=f"del_{row['id']}"):
                st.session_state.delete_confirmation = row['id']
                st.rerun()

        if st.session_state.delete_confirmation == row['id']:
            st.error(f"Tem certeza que deseja excluir o ASO de **{row['nome_funcionario']}**?")
            confirm_col1, confirm_col2 = st.columns(2)
            if confirm_col1.button("SIM, EXCLUIR", key=f"confirm_del_{row['id']}", type="primary"):
                db.collection('asos').document(row['id']).delete()
                log_activity(st.session_state['username'], "ASO Deleted", f"ID: {row['id']}")
                st.session_state.delete_confirmation = None
                st.success(f"ASO de {row['nome_funcionario']} excluído.")
                st.rerun()
            if confirm_col2.button("Cancelar", key=f"cancel_del_{row['id']}"):
                st.session_state.delete_confirmation = None
                st.rerun()

    if st.session_state.expanded_aso == row['id']:
        with container:
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
