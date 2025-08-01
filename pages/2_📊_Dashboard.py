import streamlit as st
import pandas as pd
from firebase_utils import db, bucket, log_activity, firestore
from datetime import datetime, timezone
import urllib.parse

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Inicialização do Session State ---
if 'expanded_aso' not in st.session_state: st.session_state.expanded_aso = None
if 'delete_confirmation' not in st.session_state: st.session_state.delete_confirmation = None
if 'edit_aso_id' not in st.session_state: st.session_state.edit_aso_id = None

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

if df_asos.empty:
    st.info("Nenhum ASO cadastrado ainda. Vá para a página 'Lançar ASO' para adicionar o primeiro.")
    st.stop()

# --- Processamento de Dados ---
df_asos['data_vencimento'] = pd.to_datetime(df_asos['data_vencimento'])
hoje = datetime.now(timezone.utc)
df_asos['dias_para_vencer'] = (df_asos['data_vencimento'] - hoje).dt.days

def definir_status(row):
    if row.get('tipo_exame') == 'Demissional': return 'Arquivado'
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


# --- Gráficos do Dashboard ---
st.divider()
st.subheader("Análise Gráfica")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.write(f"**Vencimentos por Mês ({datetime.now().year})**")
    df_chart = df_asos[df_asos['Status'].isin(['Vencido', 'Vence em até 30 dias', 'Vence em até 60 dias'])].copy()
    current_year = datetime.now().year
    df_chart = df_chart[df_chart['data_vencimento'].dt.year == current_year]
    if df_chart.empty:
        st.info(f"Nenhum ASO vencendo em {current_year}.")
    else:
        df_chart['mes_vencimento'] = df_chart['data_vencimento'].dt.month
        vencimentos_por_mes = df_chart.groupby('mes_vencimento').size().reset_index(name='Quantidade')
        meses_pt = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
        df_grafico = pd.DataFrame({'mes_vencimento': range(1, 13)})
        df_grafico = pd.merge(df_grafico, vencimentos_por_mes, on='mes_vencimento', how='left').fillna(0)
        df_grafico['Mês'] = df_grafico['mes_vencimento'].map(meses_pt)
        ordem_meses_cronologica = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        df_grafico['Mês'] = pd.Categorical(df_grafico['Mês'], categories=ordem_meses_cronologica, ordered=True)
        df_grafico = df_grafico.sort_values('Mês')
        st.bar_chart(df_grafico.set_index('Mês')[['Quantidade']])

with chart_col2:
    st.write("**Distribuição por Tipo de Exame**")
    tipo_exame_counts = df_asos['tipo_exame'].value_counts()
    if not tipo_exame_counts.empty:
        st.bar_chart(tipo_exame_counts)
    else:
        st.info("Sem dados para exibir.")


# --- Filtros e Tabela ---
st.divider()
st.subheader("Filtros e Relação de ASOs")
filter_col1, filter_col2, filter_col3 = st.columns(3)
status_options = df_asos['Status'].unique()
status_filter = filter_col1.multiselect("Filtrar por Status", options=status_options, default=status_options)
nome_filter = filter_col2.text_input("Filtrar por Nome do Funcionário")
tipo_exame_options = df_asos['tipo_exame'].dropna().unique()
tipo_exame_filter = filter_col3.multiselect("Filtrar por Tipo de Exame", options=tipo_exame_options, default=tipo_exame_options)

df_filtrado = df_asos[(df_asos['Status'].isin(status_filter)) & (df_asos['tipo_exame'].isin(tipo_exame_filter))]
if nome_filter:
    df_filtrado = df_filtrado[df_filtrado['nome_funcionario'].str.contains(nome_filter, case=False, na=False)]

df_display = df_filtrado[['nome_funcionario', 'funcao', 'data_vencimento', 'Status', 'id']].copy()
df_display['data_vencimento'] = df_display['data_vencimento'].dt.strftime('%d/%m/%Y')

# --- Loop de Exibição com todas as Ações ---
for index, row in df_display.iterrows():
    container = st.container(border=True)
    with container:
        col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
        col1.write(f"**{row['nome_funcionario']}** ({row.get('funcao', 'N/A')})")
        col2.write(f"Vence em: {row['data_vencimento']}")
        col3.markdown(f"Status: **{row['Status']}**")

        action_col = col4.container()
        if action_col.button("👁️ Ver Detalhes", key=f"view_{row['id']}"):
            st.session_state.expanded_aso = row['id'] if st.session_state.expanded_aso != row['id'] else None
            st.rerun()

        if st.session_state.get("role") == "admin":
            if action_col.button("✏️ Editar", key=f"edit_{row['id']}"):
                st.session_state.edit_aso_id = row['id'] if st.session_state.edit_aso_id != row['id'] else None
                st.rerun()
            if action_col.button("🗑️ Excluir", key=f"del_{row['id']}"):
                st.session_state.delete_confirmation = row['id']
                st.rerun()

        if st.session_state.delete_confirmation == row['id']:
            st.error(f"Tem certeza que deseja excluir o ASO de **{row['nome_funcionario']}**?")
            confirm_col1, confirm_col2 = st.columns(2)
            if confirm_col1.button("SIM, EXCLUIR", key=f"confirm_del_{row['id']}", type="primary"):
                db.collection('asos').document(row['id']).delete()
                log_activity(st.session_state['username'], "ASO Deleted", f"ID: {row['id']}")
                st.session_state.delete_confirmation = None
                carregar_asos_firestore.clear()
                st.success(f"ASO de {row['nome_funcionario']} excluído.")
                st.rerun()
            if confirm_col2.button("Cancelar", key=f"cancel_del_{row['id']}"):
                st.session_state.delete_confirmation = None
                st.rerun()

    # --- LÓGICA DE EDIÇÃO COMPLETA ---
    if st.session_state.edit_aso_id == row['id']:
        with st.form(key=f"edit_form_{row['id']}"):
            st.subheader(f"Editando ASO de {row['nome_funcionario']}")
            
            aso_atual = db.collection('asos').document(row['id']).get().to_dict()
            
            tipos_exame = ["Admissional", "Periódico", "Demissional", "Mudança de Risco", "Retorno ao Trabalho"]
            resultados_exame = ["Apto", "Inapto", "Apto com Restrições"]
            tipo_index = tipos_exame.index(aso_atual.get('tipo_exame')) if aso_atual.get('tipo_exame') in tipos_exame else 0
            resultado_index = resultados_exame.index(aso_atual.get('resultado')) if aso_atual.get('resultado') in resultados_exame else 0
            data_exame_atual = aso_atual.get('data_exame').date() if isinstance(aso_atual.get('data_exame'), datetime) else datetime.now().date()
            data_vencimento_atual = aso_atual.get('data_vencimento').date() if isinstance(aso_atual.get('data_vencimento'), datetime) else datetime.now().date()

            edit_col1, edit_col2 = st.columns(2)
            with edit_col1:
                novo_nome = st.text_input("Nome do Funcionário", value=aso_atual.get('nome_funcionario', ''))
                novo_tipo_exame = st.selectbox("Tipo de Exame", options=tipos_exame, index=tipo_index)
                nova_data_exame = st.date_input("Data do Exame", value=data_exame_atual)
                novo_nome_medico = st.text_input("Nome do Médico", value=aso_atual.get('nome_medico', ''))
            with edit_col2:
                nova_funcao = st.text_input("Função", value=aso_atual.get('funcao', ''))
                novo_resultado = st.selectbox("Resultado", options=resultados_exame, index=resultado_index)
                nova_data_vencimento = st.date_input("Data de Vencimento", value=data_vencimento_atual)
                novo_crm_medico = st.text_input("CRM do Médico", value=aso_atual.get('crm_medico', ''))
            
            st.divider()
            st.subheader("Gerenciar Anexos")
            
            anexos_atuais = aso_atual.get('anexos', [])
            anexos_para_remover = []

            if not anexos_atuais:
                st.info("Nenhum anexo existente.")
            else:
                for i, anexo_url in enumerate(anexos_atuais):
                    anexo_col1, anexo_col2 = st.columns([4, 1])
                    file_name = urllib.parse.unquote(anexo_url.split('%2F')[-1].split('?')[0])
                    anexo_col1.markdown(f"[{file_name}]({anexo_url})")
                    if anexo_col2.checkbox("Remover", key=f"del_anexo_{row['id']}_{i}"):
                        anexos_para_remover.append(anexo_url)

            novos_anexos = st.file_uploader("Adicionar novos anexos", accept_multiple_files=True, key=f"upload_{row['id']}")

            submit_col1, submit_col2 = st.columns(2)
            if submit_col1.form_submit_button("Salvar Alterações", type="primary"):
                with st.spinner("Atualizando ASO..."):
                    for url in anexos_para_remover:
                        try:
                            path_start = url.find("/o/") + 3
                            path_end = url.find("?alt=media")
                            file_path = urllib.parse.unquote(url[path_start:path_end])
                            blob = bucket.blob(file_path)
                            blob.delete()
                        except Exception as e:
                            st.warning(f"Não foi possível remover o anexo {url}. Erro: {e}")

                    urls_novos_anexos = []
                    for arquivo in novos_anexos:
                        file_name = f"asos/{st.session_state['uid']}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{arquivo.name}"
                        blob = bucket.blob(file_name)
                        blob.upload_from_string(arquivo.getvalue(), content_type=arquivo.type)
                        blob.make_public()
                        urls_novos_anexos.append(blob.public_url)

                    anexos_finais = [url for url in anexos_atuais if url not in anexos_para_remover]
                    anexos_finais.extend(urls_novos_anexos)
                    
                    update_data = {
                        'nome_funcionario': novo_nome, 'funcao': nova_funcao, 'tipo_exame': novo_tipo_exame,
                        'resultado': novo_resultado, 'data_exame': datetime.combine(nova_data_exame, datetime.min.time()),
                        'data_vencimento': datetime.combine(nova_data_vencimento, datetime.min.time()),
                        'nome_medico': novo_nome_medico, 'crm_medico': novo_crm_medico,
                        'anexos': anexos_finais
                    }
                    
                    db.collection('asos').document(row['id']).update(update_data)
                    log_activity(st.session_state['username'], "ASO Edited", f"ID: {row['id']}")
                    st.success("ASO atualizado com sucesso!")
                    st.session_state.edit_aso_id = None
                    carregar_asos_firestore.clear()
                    st.rerun()
            
            if submit_col2.form_submit_button("Cancelar"):
                st.session_state.edit_aso_id = None
                st.rerun()

    # --- LÓGICA DE VISUALIZAÇÃO DE DETALHES ---
    elif st.session_state.expanded_aso == row['id']:
        with container:
            with st.expander("Detalhes do ASO", expanded=True):
                doc = db.collection('asos').document(row['id']).get()
                if doc.exists:
                    details = doc.to_dict()
                    
                    st.write(f"**Nome do Funcionário:** {details.get('nome_funcionario', 'N/A')}")
                    st.write(f"**Função:** {details.get('funcao', 'N/A')}")
                    st.write(f"**Tipo de Exame:** {details.get('tipo_exame', 'N/A')}")
                    st.write(f"**Resultado:** {details.get('resultado', 'N/A')}")
                    
                    data_exame = details.get('data_exame')
                    if isinstance(data_exame, datetime):
                        st.write(f"**Data do Exame:** {data_exame.strftime('%d/%m/%Y')}")
                        
                    data_vencimento = details.get('data_vencimento')
                    if isinstance(data_vencimento, datetime):
                        st.write(f"**Data de Vencimento:** {data_vencimento.strftime('%d/%m/%Y')}")
                        
                    st.write(f"**Médico:** {details.get('nome_medico', 'N/A')}")
                    st.write(f"**CRM:** {details.get('crm_medico', 'N/A')}")
                    st.write(f"**Lançado por:** {details.get('lancado_por', 'N/A')}")
                    
                    st.divider()
                    
                    anexos = details.get('anexos')
                    if anexos and isinstance(anexos, list):
                        st.write("**Anexos:**")
                        for i, anexo_url in enumerate(anexos):
                            st.markdown(f"- [Baixar Anexo {i+1}]({anexo_url})", unsafe_allow_html=True)
                    
                    elif details.get('url_arquivo_aso'):
                        st.write("**Anexo:**")
                        st.markdown(f"- [Baixar ASO]({details.get('url_arquivo_aso')})", unsafe_allow_html=True)
                    
                    else:
                        st.info("Nenhum anexo encontrado para este ASO.")
                else:
                    st.warning("Não foi possível carregar os detalhes.")
