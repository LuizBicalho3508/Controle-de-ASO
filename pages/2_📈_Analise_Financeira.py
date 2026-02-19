import streamlit as st
import pandas as pd
import io
import plotly.express as px

# --- Configuração da Página ---
st.set_page_config(page_title="Análise Financeira 360°", page_icon="📈", layout="wide")

# --- Estilos CSS Personalizados ---
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; }
    .kpi-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Funções Auxiliares ---
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
        horas = int(partes[0])
        minutos = int(partes[1])
        return horas + (minutos / 60)
    except:
        return 0.0

def processar_csv_financeiro(uploaded_file):
    stringio = io.StringIO(uploaded_file.getvalue().decode("latin-1"))
    
    dados = []
    evento_atual = None
    empresa_atual = "Desconhecida"
    competencia_atual = "N/A"
    
    linhas = stringio.readlines()
    
    # Tentativa de extrair metadados do cabeçalho
    if len(linhas) > 0:
        # Linha 1 geralmente tem o nome da empresa: "0066 - NOME DA EMPRESA";...
        partes_l1 = linhas[0].split(';')
        if len(partes_l1) > 0:
            empresa_raw = partes_l1[0].replace('"', '').strip()
            # Remove o código inicial se existir (ex: "0066 - ")
            if " - " in empresa_raw:
                empresa_atual = empresa_raw.split(" - ", 1)[1]
            else:
                empresa_atual = empresa_raw
                
    if len(linhas) > 2:
        # Linha 3 geralmente tem o período: "Período: 02/2026 à ..."
        linha_periodo = linhas[2]
        if "Período:" in linha_periodo:
            try:
                competencia_atual = linha_periodo.split("Período:")[1].split("à")[0].strip()
            except:
                pass

    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith('_'): continue
        
        # Identifica Evento
        if linha.startswith('"Evento:'):
            evento_atual = linha.replace('"Evento:', '').replace('"', '').strip()
            # Remove código do evento se houver (ex: "37 Horas Extras")
            # Opcional: manter nome completo
            continue
            
        if "Total do Evento" in linha or "Total da Empresa" in linha or "Relação de Eventos" in linha:
            continue
            
        partes = linha.split(';')
        
        # Validação básica de linha de dados
        if len(partes) >= 6 and partes[0].replace('"', '').isdigit():
            try:
                func_id = partes[0].replace('"', '')
                nome = partes[1].replace('"', '')
                valor_raw = partes[-1].replace('"', '')
                ref_raw = partes[-2].replace('"', '')
                situacao = partes[-3].replace('"', '')
                cargo_nome = partes[-4].replace('"', '')
                
                # Ajuste se cargo for numérico (às vezes desloca)
                if cargo_nome.replace('.','').isdigit():
                     cargo_nome = partes[2].replace('"', '')

                dados.append({
                    'Empresa': empresa_atual,
                    'Competência': competencia_atual,
                    'ID Func': func_id,
                    'Nome': nome,
                    'Cargo': cargo_nome,
                    'Situação': situacao,
                    'Referência Original': ref_raw,
                    'Horas Decimais': converter_horas(ref_raw),
                    'Valor (R$)': converter_valor_monetario(valor_raw),
                    'Tipo de Evento': evento_atual,
                    'Arquivo': uploaded_file.name
                })
            except:
                continue

    return pd.DataFrame(dados)

# --- Título ---
st.title("📊 Inteligência Financeira & Folha")
st.markdown("Análise consolidada de relatórios de eventos (Ficha Financeira).")

# --- Upload ---
uploaded_files = st.file_uploader(
    "📂 Carregar Relatórios CSV (Multiselect disponível)", 
    type=["csv"], 
    accept_multiple_files=True,
    help="Você pode selecionar arquivos de diferentes empresas ao mesmo tempo."
)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        dfs.append(processar_csv_financeiro(file))
    
    if not dfs:
        st.stop()
        
    df_raw = pd.concat(dfs, ignore_index=True)
    
    if df_raw.empty:
        st.warning("Nenhum dado extraído. Verifique o layout dos arquivos.")
        st.stop()

    # --- Sidebar de Filtros ---
    with st.sidebar:
        st.header("🔍 Filtros Globais")
        
        # Filtro de Empresa
        empresas = sorted(df_raw['Empresa'].unique())
        sel_empresas = st.multiselect("Filtrar Empresas", companies := empresas, default=companies)
        
        # Filtro de Competência
        competencias = sorted(df_raw['Competência'].unique())
        sel_competencias = st.multiselect("Filtrar Competência (Mês)", competencias, default=competencias)
        
        # Filtro de Cargo
        cargos = sorted(df_raw['Cargo'].unique())
        sel_cargos = st.multiselect("Filtrar Cargos", cargos, default=cargos)
        
        # Filtro de Evento
        eventos = sorted(df_raw['Tipo de Evento'].unique())
        sel_eventos = st.multiselect("Filtrar Eventos", eventos, default=eventos)

    # Aplicação dos Filtros
    df = df_raw[
        (df_raw['Empresa'].isin(sel_empresas)) &
        (df_raw['Competência'].isin(sel_competencias)) &
        (df_raw['Cargo'].isin(sel_cargos)) &
        (df_raw['Tipo de Evento'].isin(sel_eventos))
    ]

    if df.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
        st.stop()

    # --- KPIs Principais ---
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    
    total_custo = df['Valor (R$)'].sum()
    total_horas = df['Horas Decimais'].sum()
    qtd_func = df['ID Func'].nunique()
    media_func = total_custo / qtd_func if qtd_func else 0
    
    col1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("⏱️ Total Horas Pagas", f"{total_horas:,.0f}h")
    col3.metric("👥 Colaboradores", qtd_func)
    col4.metric("📊 Custo Médio / Colab.", f"R$ {media_func:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- Abas de Análise ---
    st.divider()
    tab_geral, tab_empresas, tab_inteligencia, tab_dados = st.tabs([
        "🏢 Visão Geral", 
        "🆚 Comparativo Empresas", 
        "🧠 Inteligência & Anomalias",
        "📄 Dados Brutos"
    ])

    # --- 1. Visão Geral ---
    with tab_geral:
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Distribuição de Custos por Tipo de Evento")
            fig_evento = px.bar(
                df.groupby('Tipo de Evento')['Valor (R$)'].sum().reset_index(), 
                x='Valor (R$)', y='Tipo de Evento', orientation='h',
                text_auto='.2s', color='Valor (R$)', color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_evento, use_container_width=True)
            
        with c2:
            st.subheader("Top 5 Cargos (Custo)")
            df_cargo = df.groupby('Cargo')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=False).head(5)
            fig_cargo = px.pie(df_cargo, values='Valor (R$)', names='Cargo', hole=0.4)
            st.plotly_chart(fig_cargo, use_container_width=True)

    # --- 2. Comparativo Empresas ---
    with tab_empresas:
        if len(sel_empresas) <= 1:
            st.info("Selecione mais de uma empresa na barra lateral para ver o comparativo.")
        
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            st.markdown("### Custo Total por Empresa")
            df_emp_total = df.groupby('Empresa')['Valor (R$)'].sum().reset_index()
            fig_emp1 = px.bar(df_emp_total, x='Empresa', y='Valor (R$)', color='Empresa', text_auto='.2s')
            st.plotly_chart(fig_emp1, use_container_width=True)
            
        with col_comp2:
            st.markdown("### Média de Custo por Colaborador")
            # Agrupa por empresa e conta funcionários únicos
            df_emp_avg = df.groupby('Empresa').agg({'Valor (R$)': 'sum', 'ID Func': 'nunique'}).reset_index()
            df_emp_avg['Média (R$)'] = df_emp_avg['Valor (R$)'] / df_emp_avg['ID Func']
            
            fig_emp2 = px.bar(df_emp_avg, x='Empresa', y='Média (R$)', color='Empresa', text_auto='.2f')
            st.plotly_chart(fig_emp2, use_container_width=True)
            
        st.markdown("### Detalhamento por Evento e Empresa")
        fig_heat = px.sunburst(df, path=['Empresa', 'Tipo de Evento'], values='Valor (R$)', color='Valor (R$)')
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- 3. Inteligência & Anomalias ---
    with tab_inteligencia:
        st.markdown("### 🚨 Detecção de Horas Extras Excessivas")
        
        limite_horas = st.slider("Definir limite de alerta para horas (soma de todos eventos)", 50, 300, 100)
        
        df_func_horas = df.groupby(['Nome', 'Empresa', 'Cargo'])['Horas Decimais'].sum().reset_index()
        outliers = df_func_horas[df_func_horas['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
        
        if not outliers.empty:
            st.warning(f"Foram encontrados {len(outliers)} colaboradores com mais de {limite_horas} horas registradas no período.")
            st.dataframe(
                outliers.style.format({'Horas Decimais': '{:.2f}'}).background_gradient(cmap='Reds', subset=['Horas Decimais']),
                use_container_width=True
            )
            
            st.markdown("### 🏆 Ranking de Maiores Recebimentos (Valor Líquido Eventos)")
            df_top_recebimento = df.groupby(['Nome', 'Empresa'])['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=False).head(10)
            st.bar_chart(df_top_recebimento.set_index('Nome')['Valor (R$)'])
            
        else:
            st.success(f"Nenhum colaborador ultrapassou o limite de {limite_horas} horas.")

    # --- 4. Dados Brutos ---
    with tab_dados:
        st.dataframe(
            df[['Empresa', 'Competência', 'Nome', 'Cargo', 'Tipo de Evento', 'Referência Original', 'Valor (R$)', 'Situação']],
            use_container_width=True,
            hide_index=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar CSV Filtrado", data=csv, file_name="analise_financeira_filtrada.csv", mime="text/csv")

else:
    # Tela inicial vazia
    st.info("👆 Utilize o menu superior para carregar os arquivos CSV e iniciar a análise.")
