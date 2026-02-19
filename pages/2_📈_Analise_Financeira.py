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

# --- FUNÇÕES DE BANCO DE DADOS (DADOS) ---

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

# --- FUNÇÕES DE MAPEAMENTO (CONFIGURAÇÃO) ---

def carregar_mapa_cargos():
    """Carrega regra geral: Cargo -> Área"""
    doc = db.collection('parametros').document('mapeamento_areas').get()
    return doc.to_dict().get('mapa', {}) if doc.exists else {}

def salvar_mapa_cargos(novo_mapa):
    db.collection('parametros').document('mapeamento_areas').set({'mapa': novo_mapa})

def carregar_mapa_excecoes():
    """Carrega regra específica: Nome -> Área"""
    doc = db.collection('parametros').document('mapeamento_excecoes').get()
    return doc.to_dict().get('mapa', {}) if doc.exists else {}

def salvar_mapa_excecoes(novo_mapa):
    db.collection('parametros').document('mapeamento_excecoes').set({'mapa': novo_mapa})

# --- INTERFACE PRINCIPAL ---

try:
    st.sidebar.image("logobd.png", width=300)
except: pass

st.title("📊 Análise Financeira & Folha")

tab_dashboard, tab_config = st.tabs(["📈 Dashboard Analítico", "⚙️ Configuração de Áreas"])

# ==============================================================================
# ABA 1: DASHBOARD
# ==============================================================================
with tab_dashboard:
    modo_uso = st.sidebar.radio("Fonte de Dados:", ["🗄️ Consultar Banco de Dados", "📂 Fazer Upload (Novos Dados)"])
    
    # Lógica de Carregamento
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

    # Renderização
    if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
        df_full = st.session_state['df_financeiro'].copy()
        
        # --- LÓGICA DE APLICAÇÃO DAS ÁREAS (HIERARQUIA) ---
        mapa_cargos = carregar_mapa_cargos()     # Regra Geral
        mapa_excecoes = carregar_mapa_excecoes() # Regra Específica
        
        def definir_area(row):
            # 1. Tenta achar o Nome na lista de exceções
            if row['Nome'] in mapa_excecoes and mapa_excecoes[row['Nome']]:
                return mapa_excecoes[row['Nome']]
            # 2. Se não achar, usa o Cargo
            return mapa_cargos.get(row['Cargo'], 'Não Definido')
            
        df_full['Area'] = df_full.apply(definir_area, axis=1)
        # --------------------------------------------------

        st.divider()
        
        with st.expander("🔎 Refinar Visualização (Filtros: Área, Cargo, Evento)", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            areas_disp = sorted(df_full['Area'].unique())
            sel_areas = f_col1.multiselect("Filtrar Áreas", areas_disp, default=areas_disp)
            
            # Filtros dinâmicos
            df_area_filtered = df_full[df_full['Area'].isin(sel_areas)]
            cargos_disp = sorted(df_area_filtered['Cargo'].unique())
            sel_cargos = f_col2.multiselect("Filtrar Cargos", cargos_disp, default=cargos_disp)
            
            eventos_disp = sorted(df_full['Tipo de Evento'].unique())
            sel_eventos = f_col3.multiselect("Filtrar Eventos", eventos_disp, default=eventos_disp)

        df = df_full[
            (df_full['Area'].isin(sel_areas)) &
            (df_full['Cargo'].isin(sel_cargos)) &
            (df_full['Tipo de Evento'].isin(sel_eventos))
        ]

        if df.empty:
            st.warning("Sem dados para os filtros selecionados.")
        else:
            # KPIs e Gráficos (Mesma estrutura de antes)
            total_custo = df['Valor (R$)'].sum()
            total_horas = df['Horas Decimais'].sum()
            qtd_colab = df['ID Func'].nunique()
            media = total_custo / qtd_colab if qtd_colab else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            k2.metric("⏱️ Horas Totais", f"{total_horas:,.1f}")
            k3.metric("👥 Colaboradores", qtd_colab)
            k4.metric("📊 Ticket Médio", f"R$ {media:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            subtab1, subtab2, subtab3 = st.tabs(["🏢 Visão por Área & Empresa", "🧠 Inteligência", "📑 Tabela Detalhada"])

            with subtab1:
                col_viz1, col_viz2 = st.columns(2)
                with col_viz1:
                    st.markdown("#### Custo por Área (Setor)")
                    df_area = df.groupby('Area')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=True)
                    fig_area = px.bar(df_area, x='Valor (R$)', y='Area', orientation='h', text_auto='.2s')
                    st.plotly_chart(fig_area, use_container_width=True)
                with col_viz2:
                    st.markdown("#### Custo por Empresa")
                    df_emp = df.groupby('Empresa')['Valor (R$)'].sum().reset_index()
                    fig_emp = px.pie(df_emp, values='Valor (R$)', names='Empresa', hole=0.4)
                    st.plotly_chart(fig_emp, use_container_width=True)
                
                st.markdown("#### Detalhamento: Área > Cargo > Evento")
                fig_sun = px.sunburst(df, path=['Area', 'Cargo', 'Tipo de Evento'], values='Valor (R$)', color='Valor (R$)')
                st.plotly_chart(fig_sun, use_container_width=True)

            with subtab2:
                limite_horas = st.number_input("Alerta Horas >", value=100)
                df_out = df.groupby(['Nome', 'Empresa', 'Area', 'Cargo'])['Horas Decimais'].sum().reset_index()
                outliers = df_out[df_out['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
                if not outliers.empty:
                    st.warning(f"{len(outliers)} pessoas acima do limite.")
                    outliers['Horas'] = outliers['Horas Decimais'].apply(formatar_horas_decimal_para_str)
                    st.dataframe(outliers[['Nome', 'Empresa', 'Area', 'Horas', 'Cargo']], use_container_width=True)
                else: st.success("Tudo OK.")

            with subtab3:
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
# ABA 2: CONFIGURAÇÃO DE ÁREAS
# ==============================================================================
with tab_config:
    st.header("⚙️ Configuração de Áreas")
    st.markdown("Defina a estrutura organizacional. O sistema verifica primeiro se há uma exceção para a pessoa; se não houver, usa a regra do cargo.")

    # Divide em duas colunas/expanders
    c_config1, c_config2 = st.columns(2)

    # --- PARTE 1: REGRA GERAL (CARGOS) ---
    with c_config1:
        st.subheader("1. Regra Geral (Por Cargo)")
        st.caption("A maioria dos funcionários seguirá essa regra.")
        
        with st.spinner("Carregando mapa de cargos..."):
            mapa_cargos = carregar_mapa_cargos()
            
        # Pega lista de cargos
        if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
            cargos_sistema = sorted(st.session_state['df_financeiro']['Cargo'].unique())
        else:
            cargos_sistema = sorted(list(mapa_cargos.keys()))
            
        if not cargos_sistema:
            st.info("Carregue dados primeiro para configurar.")
        else:
            todos_cargos = sorted(list(set(cargos_sistema) | set(mapa_cargos.keys())))
            df_editor_cargos = pd.DataFrame([{"Cargo": c, "Área Padrão": mapa_cargos.get(c, "")} for c in todos_cargos])
            
            df_editado_cargos = st.data_editor(
                df_editor_cargos,
                key="editor_cargos",
                column_config={"Cargo": st.column_config.TextColumn(disabled=True)},
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            if st.button("💾 Salvar Regras de Cargos", type="primary"):
                novo_mapa = pd.Series(df_editado_cargos['Área Padrão'].values, index=df_editado_cargos['Cargo']).to_dict()
                novo_mapa = {k: v for k, v in novo_mapa.items() if v and str(v).strip() != ""}
                salvar_mapa_cargos(novo_mapa)
                st.success("Regras de cargos atualizadas!")

    # --- PARTE 2: EXCEÇÕES (PESSOAS) ---
    with c_config2:
        st.subheader("2. Exceções (Por Pessoa)")
        st.caption("Use para pessoas que têm um cargo genérico mas trabalham em outra área.")
        
        mapa_excecoes = carregar_mapa_excecoes()
        
        # Seleção de Cargo para filtrar pessoas
        st.markdown("**Adicionar Nova Exceção:**")
        
        if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
            cargos_disponiveis = sorted(st.session_state['df_financeiro']['Cargo'].unique())
            cargo_filtro = st.selectbox("Selecione um Cargo para ver as pessoas:", ["Todos"] + cargos_disponiveis)
            
            df_pessoas = st.session_state['df_financeiro'][['Nome', 'Cargo']].drop_duplicates().sort_values('Nome')
            if cargo_filtro != "Todos":
                df_pessoas = df_pessoas[df_pessoas['Cargo'] == cargo_filtro]
            
            # Prepara DF de Edição
            lista_pessoas = []
            for _, row in df_pessoas.iterrows():
                nome = row['Nome']
                cargo = row['Cargo']
                # Se já tem exceção, mostra a área da exceção. Senão mostra vazio
                area_atual = mapa_excecoes.get(nome, "")
                lista_pessoas.append({"Nome": nome, "Cargo": cargo, "Área (Exceção)": area_atual})
            
            df_editor_pessoas = pd.DataFrame(lista_pessoas)
            
            df_editado_pessoas = st.data_editor(
                df_editor_pessoas,
                key="editor_pessoas",
                column_config={
                    "Nome": st.column_config.TextColumn(disabled=True),
                    "Cargo": st.column_config.TextColumn(disabled=True),
                    "Área (Exceção)": st.column_config.TextColumn(help="Preencha APENAS se for diferente do padrão do cargo")
                },
                use_container_width=True,
                height=320,
                hide_index=True
            )
            
            if st.button("💾 Salvar Exceções"):
                # Atualiza apenas as que foram preenchidas
                novas_excecoes = pd.Series(df_editado_pessoas['Área (Exceção)'].values, index=df_editado_pessoas['Nome']).to_dict()
                
                # Mescla com as exceções existentes (para não perder as de outros cargos que não estão na tela)
                mapa_final = mapa_excecoes.copy()
                for nome, area in novas_excecoes.items():
                    if area and str(area).strip() != "":
                        mapa_final[nome] = area
                    elif nome in mapa_final:
                        # Se limpou o campo, remove a exceção
                        del mapa_final[nome]
                
                salvar_mapa_excecoes(mapa_final)
                st.success("Exceções atualizadas!")
        else:
            st.info("Carregue dados no Dashboard para listar os funcionários.")
