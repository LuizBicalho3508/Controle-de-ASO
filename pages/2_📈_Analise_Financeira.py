import streamlit as st
import pandas as pd
import io
import plotly.express as px
from firebase_utils import db
from google.cloud.firestore import FieldPath # IMPORTANTE: Importação necessária para corrigir o erro do acento

# --- Configuração da Página ---
st.set_page_config(page_title="Análise Financeira & Histórico", page_icon="📈", layout="wide")

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Funções Auxiliares (Conversão e Tratamento) ---

def converter_valor_monetario(valor_str):
    if pd.isna(valor_str): return 0.0
    try:
        limpo = str(valor_str).replace('.', '').replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def converter_horas(hora_str):
    if pd.isna(hora_str): return 0.0
    try:
        limpo = str(hora_str).lower().replace('hs', '').strip()
        partes = limpo.split(':')
        return int(partes[0]) + (int(partes[1]) / 60)
    except:
        return 0.0

def formatar_horas_decimal_para_str(horas_decimal):
    try:
        horas = int(horas_decimal)
        minutos = int((horas_decimal - horas) * 60)
        return f"{horas:02d}:{minutos:02d}"
    except:
        return "00:00"

def extrair_metadados(linhas):
    empresa = "Empresa Desconhecida"
    competencia = "N/A"
    for linha in linhas[:20]:
        linha = linha.strip()
        if " - " in linha and ";" in linha and ("Pág:" in linha or "Pag:" in linha):
            partes = linha.split(';')
            if len(partes) > 0:
                raw_emp = partes[0].replace('"', '').strip()
                empresa = raw_emp.split(" - ", 1)[1] if " - " in raw_emp else raw_emp
        if "Período:" in linha:
            try:
                competencia = linha.split(':')[1].split('à')[0].replace('"', '').strip()
            except: pass
    return empresa, competencia

@st.cache_data(show_spinner=False)
def processar_csv_financeiro(file_content, file_name):
    try:
        decoded = file_content.decode("utf-8")
    except UnicodeDecodeError:
        decoded = file_content.decode("latin-1")
        
    stringio = io.StringIO(decoded)
    linhas = stringio.readlines()
    empresa_atual, competencia_atual = extrair_metadados(linhas)
    
    dados = []
    evento_atual = None
    
    for linha in linhas:
        linha_clean = linha.strip()
        if not linha_clean or linha_clean.startswith('_') or "Total" in linha_clean: continue
        
        if linha_clean.startswith('"Evento:') or linha_clean.startswith('Evento:'):
            evento_atual = linha_clean.replace('"Evento:', '').replace('Evento:', '').replace('"', '').strip()
            continue
            
        partes = linha_clean.split(';')
        if len(partes) >= 6 and partes[0].replace('"', '').strip().isdigit():
            try:
                cargo_nome = partes[-4].replace('"', '').strip()
                if cargo_nome.replace('.', '').isdigit(): cargo_nome = partes[2].replace('"', '').strip()

                dados.append({
                    'Empresa': empresa_atual,
                    'Competência': competencia_atual,
                    'ID Func': partes[0].replace('"', '').strip(),
                    'Nome': partes[1].replace('"', '').strip(),
                    'Cargo': cargo_nome,
                    'Referência Original': partes[-2].replace('"', '').strip(),
                    'Horas Decimais': converter_horas(partes[-2].replace('"', '').strip()),
                    'Valor (R$)': converter_valor_monetario(partes[-1].replace('"', '').strip()),
                    'Tipo de Evento': evento_atual,
                    'Arquivo': file_name
                })
            except: continue
    return pd.DataFrame(dados)

# --- Funções de Banco de Dados (Firestore) ---

def salvar_no_firestore(df_para_salvar):
    """Salva o DataFrame no Firestore em Lotes (Batches)"""
    collection_ref = db.collection('folha_eventos')
    batch = db.batch()
    count = 0
    total_ops = 0
    
    progress_bar = st.progress(0, text="Iniciando gravação no banco...")
    total_linhas = len(df_para_salvar)

    for index, row in df_para_salvar.iterrows():
        # Cria um ID ÚNICO para evitar duplicatas
        evento_safe = "".join(c for c in row['Tipo de Evento'] if c.isalnum())
        doc_id = f"{row['Empresa']}_{row['Competência'].replace('/', '-')}_{row['ID Func']}_{evento_safe}"
        
        doc_ref = collection_ref.document(doc_id)
        dados_row = row.to_dict()
        batch.set(doc_ref, dados_row)
        
        count += 1
        total_ops += 1
        
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            progress_bar.progress(min(total_ops / total_linhas, 1.0), text=f"Salvando registro {total_ops} de {total_linhas}...")

    if count > 0:
        batch.commit()
        
    progress_bar.empty()
    return total_ops

def carregar_filtros_disponiveis():
    """Busca opções para filtros usando FieldPath para evitar erros de acentuação"""
    # CORREÇÃO AQUI: Usando FieldPath e passando argumentos posicionais para select
    docs = db.collection('folha_eventos').select('Empresa', FieldPath('Competência')).stream()
    empresas = set()
    competencias = set()
    
    for doc in docs:
        d = doc.to_dict()
        if 'Empresa' in d: empresas.add(d['Empresa'])
        if 'Competência' in d: competencias.add(d['Competência'])
        
    return sorted(list(empresas)), sorted(list(competencias))

@st.cache_data(ttl=300)
def carregar_dados_do_banco(empresas_sel, competencias_sel):
    """Carrega dados filtrados do banco usando FieldPath"""
    if not empresas_sel or not competencias_sel:
        return pd.DataFrame()
        
    registros = []
    collection = db.collection('folha_eventos')
    
    for emp in empresas_sel:
        # CORREÇÃO AQUI: Usando FieldPath('Competência') no lugar da string simples
        query = collection.where('Empresa', '==', emp).where(FieldPath('Competência'), 'in', competencias_sel).stream()
        for doc in query:
            registros.append(doc.to_dict())
            
    return pd.DataFrame(registros)


# --- Interface Principal ---

st.sidebar.image("logobd.png", use_container_width=True) if "logobd.png" in "logobd.png" else None
st.title("📊 Análise Financeira & Folha")

# --- Seletor de Modo ---
modo_uso = st.sidebar.radio("Fonte de Dados:", ["📂 Fazer Upload (Novos Dados)", "🗄️ Consultar Banco de Dados"])

df_trabalho = pd.DataFrame()

# ==============================================================================
# MODO 1: UPLOAD (LER CSV E SALVAR)
# ==============================================================================
if modo_uso == "📂 Fazer Upload (Novos Dados)":
    st.subheader("Importação de Arquivos da Folha")
    uploaded_files = st.file_uploader("Carregar CSVs", type=["csv"], accept_multiple_files=True)
    
    if uploaded_files:
        dfs = []
        for file in uploaded_files:
            dfs.append(processar_csv_financeiro(file.getvalue(), file.name))
        
        if dfs:
            df_trabalho = pd.concat(dfs, ignore_index=True)
            
            if not df_trabalho.empty:
                st.success(f"{len(df_trabalho)} registros processados prontos para análise ou salvamento.")
                
                # --- Botão de Salvar ---
                col_save1, col_save2 = st.columns([2, 1])
                with col_save1:
                    st.info("💡 Verifique os dados abaixo. Se estiver tudo certo, clique em Salvar para gravar no histórico.")
                with col_save2:
                    if st.button("💾 SALVAR NO BANCO DE DADOS", type="primary"):
                        try:
                            qtd = salvar_no_firestore(df_trabalho)
                            st.balloons()
                            st.success(f"Sucesso! {qtd} registros foram gravados/atualizados no banco de dados.")
                        except Exception as e:
                            st.error(f"Erro ao salvar no banco: {e}")
            else:
                st.warning("Arquivos vazios ou formato inválido.")

# ==============================================================================
# MODO 2: CONSULTA (LER DO FIRESTORE)
# ==============================================================================
else:
    st.subheader("Consulta Histórica")
    
    with st.spinner("Carregando opções de filtro..."):
        try:
            opcoes_empresas, opcoes_competencias = carregar_filtros_disponiveis()
        except Exception as e:
            st.error(f"Erro ao conectar no banco: {e}")
            opcoes_empresas, opcoes_competencias = [], []
    
    with st.sidebar:
        st.divider()
        st.header("Filtros do Banco")
        filtro_empresa_db = st.multiselect("Empresas", opcoes_empresas, default=opcoes_empresas)
        filtro_competencia_db = st.multiselect("Competências", opcoes_competencias, default=[opcoes_competencias[-1]] if opcoes_competencias else [])

    if st.button("🔍 Buscar Dados"):
        if not filtro_empresa_db or not filtro_competencia_db:
            st.warning("Selecione pelo menos uma Empresa e uma Competência.")
        else:
            with st.spinner("Baixando dados do nuvem..."):
                df_trabalho = carregar_dados_do_banco(filtro_empresa_db, filtro_competencia_db)
                if df_trabalho.empty:
                    st.warning("Nenhum dado encontrado para os filtros selecionados.")
                else:
                    st.toast(f"{len(df_trabalho)} registros carregados!", icon="✅")

# ==============================================================================
# DASHBOARD (COMUM AOS DOIS MODOS)
# ==============================================================================

if not df_trabalho.empty:
    st.divider()
    
    # --- Filtros Locais (Pós-carregamento) ---
    with st.expander("🔎 Refinar Visualização (Filtros Locais)", expanded=False):
        col_f1, col_f2 = st.columns(2)
        cargos_disp = sorted(df_trabalho['Cargo'].unique())
        eventos_disp = sorted(df_trabalho['Tipo de Evento'].unique())
        
        sel_cargos = col_f1.multiselect("Filtrar Cargos", cargos_disp, default=cargos_disp)
        sel_eventos = col_f2.multiselect("Filtrar Eventos", eventos_disp, default=eventos_disp)
    
    df = df_trabalho[
        (df_trabalho['Cargo'].isin(sel_cargos)) &
        (df_trabalho['Tipo de Evento'].isin(sel_eventos))
    ]
    
    if df.empty:
        st.warning("Sem dados após filtros locais.")
        st.stop()
    
    # --- KPIs ---
    total_custo = df['Valor (R$)'].sum()
    total_horas = df['Horas Decimais'].sum()
    qtd_colab = df['ID Func'].nunique()
    media = total_custo / qtd_colab if qtd_colab else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    c2.metric("⏱️ Horas Totais", f"{total_horas:,.1f}")
    c3.metric("👥 Colaboradores", qtd_colab)
    c4.metric("📊 Ticket Médio", f"R$ {media:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- Abas ---
    tab1, tab2, tab3 = st.tabs(["🏢 Visão Geral & Comparativo", "🧠 Inteligência (Outliers)", "📑 Tabela Detalhada"])

    # ABA 1: Visão Geral
    with tab1:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("#### Custo por Empresa")
            fig_emp = px.bar(df.groupby('Empresa')['Valor (R$)'].sum().reset_index(), x='Empresa', y='Valor (R$)', color='Empresa', text_auto='.2s')
            st.plotly_chart(fig_emp, use_container_width=True)
        with col_g2:
            st.markdown("#### Custo por Tipo de Evento")
            fig_evt = px.pie(df.groupby('Tipo de Evento')['Valor (R$)'].sum().reset_index(), values='Valor (R$)', names='Tipo de Evento', hole=0.4)
            st.plotly_chart(fig_evt, use_container_width=True)

    # ABA 2: Outliers
    with tab2:
        limite_horas = st.number_input("Alerta de Horas Acima de:", value=100)
        df_out = df.groupby(['Nome', 'Empresa', 'Cargo'])['Horas Decimais'].sum().reset_index()
        outliers = df_out[df_out['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
        if not outliers.empty:
            st.warning(f"{len(outliers)} colaboradores excederam {limite_horas} horas.")
            outliers['Horas'] = outliers['Horas Decimais'].apply(formatar_horas_decimal_para_str)
            st.dataframe(outliers[['Nome', 'Empresa', 'Horas', 'Cargo']], use_container_width=True)
        else:
            st.success("Tudo dentro dos conformes.")

    # ABA 3: Tabela Detalhada (Pivot)
    with tab3:
        def cat_evento(e):
            e = str(e).upper()
            if "60%" in e: return "60%"
            if "DSR" in e: return "DSR"
            return "OUTROS"
        
        df['Cat'] = df['Tipo de Evento'].apply(cat_evento)
        
        pivot = df.pivot_table(
            index=['Empresa', 'Competência', 'Nome', 'Cargo'],
            columns='Cat',
            values=['Horas Decimais', 'Valor (R$)'],
            aggfunc='sum',
            fill_value=0
        )
        
        pivot.columns = [f'{c[0]}|{c[1]}' for c in pivot.columns]
        pivot = pivot.reset_index()
        
        for c in ['Valor (R$)|60%', 'Valor (R$)|DSR', 'Horas Decimais|60%', 'Horas Decimais|DSR']:
            if c not in pivot.columns: pivot[c] = 0.0
            
        pivot['Total (R$)'] = pivot['Valor (R$)|60%'] + pivot['Valor (R$)|DSR']
        if 'Valor (R$)|OUTROS' in pivot.columns: pivot['Total (R$)'] += pivot['Valor (R$)|OUTROS']
        
        final = pivot.copy()
        final['Banco 60%'] = final['Horas Decimais|60%'].apply(formatar_horas_decimal_para_str)
        final['Horas DSR'] = final['Horas Decimais|DSR'].apply(formatar_horas_decimal_para_str)
        
        cols_show = ['Empresa', 'Competência', 'Nome', 'Cargo', 'Banco 60%', 'Valor (R$)|60%', 'Horas DSR', 'Valor (R$)|DSR', 'Total (R$)']
        cols_show = [c for c in cols_show if c in final.columns]
        
        st.dataframe(final[cols_show].style.format({"Valor (R$)|60%": "R$ {:,.2f}", "Valor (R$)|DSR": "R$ {:,.2f}", "Total (R$)": "R$ {:,.2f}"}), use_container_width=True)
