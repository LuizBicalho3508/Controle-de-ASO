import streamlit as st
import pandas as pd
import io
import plotly.express as px
from firebase_utils import db

# --- CORREÇÃO DE IMPORTAÇÃO (FieldPath) ---
try:
    from google.cloud.firestore import FieldPath
except ImportError:
    try:
        from google.cloud.firestore_v1.field_path import FieldPath
    except ImportError:
        try:
            from google.cloud import firestore
            FieldPath = firestore.FieldPath
        except Exception:
            FieldPath = None

# --- Configuração da Página ---
st.set_page_config(page_title="Análise Financeira & Histórico", page_icon="📈", layout="wide")

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- INICIALIZAÇÃO DO STATE ---
if 'df_financeiro' not in st.session_state:
    st.session_state['df_financeiro'] = pd.DataFrame()

# --- FUNÇÕES AUXILIARES ---
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

# --- FUNÇÕES DE BANCO DE DADOS (DADOS E MAPEAMENTO) ---

def salvar_no_firestore(df_para_salvar):
    collection_ref = db.collection('folha_eventos')
    batch = db.batch()
    count = 0
    total_ops = 0
    progress_bar = st.progress(0, text="Iniciando gravação...")
    total_linhas = len(df_para_salvar)

    for index, row in df_para_salvar.iterrows():
        comp_safe = str(row['Competência']).replace('/', '-')
        evento_safe = "".join(c for c in str(row['Tipo de Evento']) if c.isalnum())
        doc_id = f"{row['Empresa']}_{comp_safe}_{row['ID Func']}_{evento_safe}"
        
        doc_ref = collection_ref.document(doc_id)
        batch.set(doc_ref, row.to_dict())
        count += 1
        total_ops += 1
        
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            progress_bar.progress(min(total_ops / total_linhas, 1.0), text=f"Salvando {total_ops}/{total_linhas}...")

    if count > 0: batch.commit()
    progress_bar.empty()
    return total_ops

def carregar_filtros_disponiveis():
    try:
        docs = db.collection('folha_eventos').select(['Empresa', 'Competência']).stream()
    except:
        docs = db.collection('folha_eventos').stream()
    empresas, competencias = set(), set()
    for doc in docs:
        d = doc.to_dict()
        if 'Empresa' in d: empresas.add(d['Empresa'])
        if 'Competência' in d: competencias.add(d['Competência'])
    return sorted(list(empresas)), sorted(list(competencias))

@st.cache_data(ttl=300)
def carregar_dados_do_banco(empresas_sel, competencias_sel):
    if not empresas_sel: return pd.DataFrame()
    registros = []
    collection = db.collection('folha_eventos')
    for emp in empresas_sel:
        query = collection.where('Empresa', '==', emp).stream()
        for doc in query:
            d = doc.to_dict()
            if d.get('Competência') in competencias_sel:
                registros.append(d)
    return pd.DataFrame(registros)

# --- FUNÇÕES DE MAPEAMENTO DE ÁREAS (CONFIGURAÇÃO) ---

def carregar_mapa_areas():
    """Carrega o dicionário Cargo -> Área do Firestore"""
    doc = db.collection('parametros').document('mapeamento_areas').get()
    if doc.exists:
        return doc.to_dict().get('mapa', {})
    return {}

def salvar_mapa_areas(novo_mapa):
    """Salva o dicionário Cargo -> Área no Firestore"""
    db.collection('parametros').document('mapeamento_areas').set({'mapa': novo_mapa})

# --- INTERFACE PRINCIPAL ---

try:
    st.sidebar.image("logobd.png", width=300)
except: pass

st.title("📊 Análise Financeira & Folha")

# --- CONTROLE DE ABAS (PRINCIPAL) ---
tab_dashboard, tab_config = st.tabs(["📈 Dashboard Analítico", "⚙️ Configuração de Áreas"])

# ==============================================================================
# ABA 1: DASHBOARD (Lógica de Carregamento e Visualização)
# ==============================================================================
with tab_dashboard:
    modo_uso = st.sidebar.radio("Fonte de Dados:", ["🗄️ Consultar Banco de Dados", "📂 Fazer Upload (Novos Dados)"])
    
    # --- BLOCO DE CARREGAMENTO DE DADOS ---
    if modo_uso == "🗄️ Consultar Banco de Dados":
        st.subheader("Consulta Histórica")
        with st.spinner("Carregando opções..."):
            try:
                opcoes_empresas, opcoes_competencias = carregar_filtros_disponiveis()
            except Exception as e:
                st.error(f"Erro BD: {e}")
                opcoes_empresas, opcoes_competencias = [], []
        
        with st.sidebar:
            st.divider()
            st.header("Filtros Globais")
            filtro_empresa_db = st.multiselect("Empresas", opcoes_empresas, default=opcoes_empresas)
            filtro_competencia_db = st.multiselect("Competências", opcoes_competencias, default=[opcoes_competencias[-1]] if opcoes_competencias else [])

        if st.button("🔍 Buscar Dados"):
            if not filtro_empresa_db or not filtro_competencia_db:
                st.warning("Selecione Empresa e Competência.")
            else:
                with st.spinner("Buscando dados..."):
                    df_temp = carregar_dados_do_banco(filtro_empresa_db, filtro_competencia_db)
                    if df_temp.empty:
                        st.warning("Nenhum dado encontrado.")
                    else:
                        st.session_state['df_financeiro'] = df_temp
                        st.success(f"{len(df_temp)} registros carregados!")
    else:
        st.subheader("Importação de CSV")
        uploaded_files = st.file_uploader("Carregar CSVs", type=["csv"], accept_multiple_files=True)
        if uploaded_files:
            dfs = []
            for file in uploaded_files:
                dfs.append(processar_csv_financeiro(file.getvalue(), file.name))
            if dfs:
                df_temp = pd.concat(dfs, ignore_index=True)
                if not df_temp.empty:
                    st.session_state['df_financeiro'] = df_temp
                    st.success(f"{len(df_temp)} processados.")
                    if st.button("💾 SALVAR TUDO NO BANCO", type="primary"):
                        salvar_no_firestore(df_temp)
                        st.success("Salvo!")

    # --- RENDERIZAÇÃO DO DASHBOARD ---
    if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
        df_full = st.session_state['df_financeiro'].copy()
        
        # 1. APLICAÇÃO DO MAPEAMENTO DE ÁREAS
        mapa_areas = carregar_mapa_areas()
        # Cria a coluna Área baseada no mapa, se não achar, põe "Não Definido"
        df_full['Area'] = df_full['Cargo'].map(mapa_areas).fillna('Não Definido')

        st.divider()
        
        # 2. FILTROS LOCAIS (COM ÁREA)
        with st.expander("🔎 Refinar Visualização (Filtros: Área, Cargo, Evento)", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            
            # Filtro de Área
            areas_disp = sorted(df_full['Area'].unique())
            sel_areas = f_col1.multiselect("Filtrar Áreas", areas_disp, default=areas_disp)
            
            # Filtro de Cargo (Dinâmico com base na Área selecionada)
            cargos_disp = sorted(df_full[df_full['Area'].isin(sel_areas)]['Cargo'].unique())
            sel_cargos = f_col2.multiselect("Filtrar Cargos", cargos_disp, default=cargos_disp)
            
            eventos_disp = sorted(df_full['Tipo de Evento'].unique())
            sel_eventos = f_col3.multiselect("Filtrar Eventos", eventos_disp, default=eventos_disp)

        # 3. FILTRAGEM DO DATAFRAME
        df = df_full[
            (df_full['Area'].isin(sel_areas)) &
            (df_full['Cargo'].isin(sel_cargos)) &
            (df_full['Tipo de Evento'].isin(sel_eventos))
        ]

        if df.empty:
            st.warning("Sem dados para os filtros selecionados.")
        else:
            # KPIs
            total_custo = df['Valor (R$)'].sum()
            total_horas = df['Horas Decimais'].sum()
            qtd_colab = df['ID Func'].nunique()
            media = total_custo / qtd_colab if qtd_colab else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            k2.metric("⏱️ Horas Totais", f"{total_horas:,.1f}")
            k3.metric("👥 Colaboradores", qtd_colab)
            k4.metric("📊 Ticket Médio", f"R$ {media:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # GRÁFICOS
            subtab1, subtab2, subtab3 = st.tabs(["🏢 Visão por Área & Empresa", "🧠 Inteligência", "📑 Tabela Detalhada"])

            with subtab1:
                col_viz1, col_viz2 = st.columns(2)
                with col_viz1:
                    st.markdown("#### Custo por Área (Setor)")
                    # Agrupa por Área e ordena
                    df_area = df.groupby('Area')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=True)
                    fig_area = px.bar(df_area, x='Valor (R$)', y='Area', orientation='h', text_auto='.2s', title="Custo Total por Área")
                    st.plotly_chart(fig_area, use_container_width=True)
                
                with col_viz2:
                    st.markdown("#### Custo por Empresa")
                    df_emp = df.groupby('Empresa')['Valor (R$)'].sum().reset_index()
                    fig_emp = px.pie(df_emp, values='Valor (R$)', names='Empresa', hole=0.4)
                    st.plotly_chart(fig_emp, use_container_width=True)
                
                # Gráfico extra: Área vs Tipo de Evento (Sunburst)
                st.markdown("#### Detalhamento: Área > Cargo > Evento")
                fig_sun = px.sunburst(df, path=['Area', 'Cargo', 'Tipo de Evento'], values='Valor (R$)', color='Valor (R$)')
                st.plotly_chart(fig_sun, use_container_width=True)

            with subtab2:
                # Inteligência
                limite_horas = st.number_input("Alerta Horas >", value=100)
                df_out = df.groupby(['Nome', 'Empresa', 'Area', 'Cargo'])['Horas Decimais'].sum().reset_index()
                outliers = df_out[df_out['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
                
                if not outliers.empty:
                    st.warning(f"{len(outliers)} pessoas acima do limite.")
                    outliers['Horas'] = outliers['Horas Decimais'].apply(formatar_horas_decimal_para_str)
                    st.dataframe(outliers[['Nome', 'Empresa', 'Area', 'Horas', 'Cargo']], use_container_width=True)
                else:
                    st.success("Tudo OK.")

            with subtab3:
                # Tabela Pivot
                def cat_evento(e):
                    e = str(e).upper()
                    if "60%" in e: return "60%"
                    if "DSR" in e: return "DSR"
                    return "OUTROS"
                
                df['Cat'] = df['Tipo de Evento'].apply(cat_evento)
                pivot = df.pivot_table(index=['Empresa', 'Area', 'Nome', 'Cargo'], columns='Cat', values=['Horas Decimais', 'Valor (R$)'], aggfunc='sum', fill_value=0)
                pivot.columns = [f'{c[0]}|{c[1]}' for c in pivot.columns]
                pivot = pivot.reset_index()
                
                for c in ['Valor (R$)|60%', 'Valor (R$)|DSR', 'Horas Decimais|60%', 'Horas Decimais|DSR']:
                    if c not in pivot.columns: pivot[c] = 0.0
                
                pivot['Total (R$)'] = pivot['Valor (R$)|60%'] + pivot['Valor (R$)|DSR']
                if 'Valor (R$)|OUTROS' in pivot.columns: pivot['Total (R$)'] += pivot['Valor (R$)|OUTROS']
                
                final = pivot.copy()
                final['Banco 60%'] = final['Horas Decimais|60%'].apply(formatar_horas_decimal_para_str)
                final['Horas DSR'] = final['Horas Decimais|DSR'].apply(formatar_horas_decimal_para_str)
                
                cols_show = ['Empresa', 'Area', 'Nome', 'Cargo', 'Banco 60%', 'Valor (R$)|60%', 'Horas DSR', 'Valor (R$)|DSR', 'Total (R$)']
                cols_show = [c for c in cols_show if c in final.columns]
                
                st.dataframe(final[cols_show].style.format({"Valor (R$)|60%": "R$ {:,.2f}", "Valor (R$)|DSR": "R$ {:,.2f}", "Total (R$)": "R$ {:,.2f}"}), use_container_width=True)

# ==============================================================================
# ABA 2: CONFIGURAÇÃO DE ÁREAS (Mapeamento)
# ==============================================================================
with tab_config:
    st.header("⚙️ Configuração de Áreas (De/Para)")
    st.markdown("Defina qual **Área** (ex: NOC, Comercial, Adm) cada **Cargo** pertence. Essas configurações são salvas no banco.")
    
    # 1. Carrega Mapa Existente
    with st.spinner("Carregando configurações..."):
        mapa_atual = carregar_mapa_areas()
    
    # 2. Identifica Cargos dos Dados Atuais (se houver) para facilitar
    cargos_identificados = []
    if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
        cargos_identificados = sorted(st.session_state['df_financeiro']['Cargo'].unique())
    else:
        # Se não tiver dados carregados, usa as chaves do mapa salvo
        cargos_identificados = sorted(list(mapa_atual.keys()))

    if not cargos_identificados:
        st.info("Nenhum cargo identificado ainda. Carregue dados na aba Dashboard primeiro.")
    else:
        # 3. Prepara DataFrame para Edição
        # Combina cargos atuais com os já salvos para garantir que nada se perca
        todos_cargos = sorted(list(set(cargos_identificados) | set(mapa_atual.keys())))
        
        data_editor_list = []
        for cargo in todos_cargos:
            data_editor_list.append({
                "Cargo": cargo,
                "Área Atribuída": mapa_atual.get(cargo, "") # Traz o salvo ou vazio
            })
        
        df_editor = pd.DataFrame(data_editor_list)
        
        # 4. Exibe Editor
        col_ed1, col_ed2 = st.columns([3, 1])
        with col_ed1:
            st.markdown("##### Editor de Atribuições")
            df_editado = st.data_editor(
                df_editor,
                column_config={
                    "Cargo": st.column_config.TextColumn("Cargo", disabled=True),
                    "Área Atribuída": st.column_config.TextColumn("Área (Digite o nome)", help="Ex: NOC, Comercial, RH")
                },
                use_container_width=True,
                height=500,
                hide_index=True
            )
        
        with col_ed2:
            st.info("ℹ️ Dica: Digite o nome da área para cada cargo. O sistema agrupará automaticamente.")
            if st.button("💾 SALVAR CONFIGURAÇÕES", type="primary"):
                try:
                    # Converte o DF editado de volta para dicionário
                    novo_mapa = pd.Series(df_editado['Área Atribuída'].values, index=df_editado['Cargo']).to_dict()
                    # Remove entradas vazias para limpar o banco
                    novo_mapa = {k: v for k, v in novo_mapa.items() if v and str(v).strip() != ""}
                    
                    salvar_mapa_areas(novo_mapa)
                    st.success("Configurações salvas com sucesso! Volte ao Dashboard para ver as atualizações.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
