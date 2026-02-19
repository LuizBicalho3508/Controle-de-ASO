import streamlit as st
import pandas as pd
import io
import plotly.express as px

# --- Configuração da Página ---
st.set_page_config(page_title="Análise Financeira 360°", page_icon="📈", layout="wide")

# --- Estilos CSS ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Tenta carregar Logo ---
try:
    st.logo("logobd.png")
except:
    pass

# --- Funções de Tratamento de Dados ---

def converter_valor_monetario(valor_str):
    """Converte '1.234,56' para float 1234.56"""
    if pd.isna(valor_str): return 0.0
    try:
        limpo = str(valor_str).replace('.', '').replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def converter_horas(hora_str):
    """Converte '123:30 hs' para horas decimais"""
    if pd.isna(hora_str): return 0.0
    try:
        limpo = str(hora_str).lower().replace('hs', '').strip()
        partes = limpo.split(':')
        horas = int(partes[0])
        minutos = int(partes[1])
        return horas + (minutos / 60)
    except:
        return 0.0

def formatar_horas_decimal_para_str(horas_decimal):
    """Converte 1.5 para '01:30' para exibição visual"""
    try:
        horas = int(horas_decimal)
        minutos = int((horas_decimal - horas) * 60)
        return f"{horas:02d}:{minutos:02d}"
    except:
        return "00:00"

def extrair_metadados(linhas):
    """
    Busca inteligente por Empresa e Período nas primeiras linhas
    """
    empresa = "Empresa Desconhecida"
    competencia = "N/A"
    
    for linha in linhas[:20]:
        linha = linha.strip()
        # Busca Nome da Empresa
        if " - " in linha and ";" in linha and ("Pág:" in linha or "Pag:" in linha):
            partes = linha.split(';')
            if len(partes) > 0:
                raw_emp = partes[0].replace('"', '').strip()
                if " - " in raw_emp:
                    empresa = raw_emp.split(" - ", 1)[1]
                else:
                    empresa = raw_emp
        
        # Busca Período
        if "Período:" in linha or "Periodo:" in linha:
            try:
                competencia = linha.split(':')[1].split('à')[0].replace('"', '').strip()
            except:
                pass
                
    return empresa, competencia

@st.cache_data(show_spinner=False)
def processar_csv_financeiro(file_content, file_name):
    """Processa o conteúdo bruto do arquivo"""
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
        
        if not linha_clean or linha_clean.startswith('_') or "Total do Evento" in linha_clean or "Total da Empresa" in linha_clean:
            continue
            
        if linha_clean.startswith('"Evento:') or linha_clean.startswith('Evento:'):
            evento_atual = linha_clean.replace('"Evento:', '').replace('Evento:', '').replace('"', '').strip()
            continue
            
        partes = linha_clean.split(';')
        
        if len(partes) >= 6 and partes[0].replace('"', '').strip().isdigit():
            try:
                func_id = partes[0].replace('"', '').strip()
                nome = partes[1].replace('"', '').strip()
                valor_raw = partes[-1].replace('"', '').strip()
                ref_raw = partes[-2].replace('"', '').strip()
                situacao = partes[-3].replace('"', '').strip()
                cargo_nome = partes[-4].replace('"', '').strip()
                
                if cargo_nome.replace('.', '').isdigit():
                     cargo_nome = partes[2].replace('"', '').strip()

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
                    'Arquivo': file_name
                })
            except Exception:
                continue

    return pd.DataFrame(dados)

# --- Interface Principal ---

st.title("📊 Inteligência Financeira & Folha")
st.markdown("Dashboard analítico para consolidação de relatórios de múltiplos CNPJs.")

# Upload
uploaded_files = st.file_uploader(
    "Carregar Relatórios CSV (Ficha Financeira)", 
    type=["csv"], 
    accept_multiple_files=True,
    help="Selecione um ou múltiplos arquivos de diferentes empresas."
)

if uploaded_files:
    dfs = []
    progresso = st.progress(0, text="Iniciando processamento...")
    
    for i, file in enumerate(uploaded_files):
        bytes_data = file.getvalue()
        df_temp = processar_csv_financeiro(bytes_data, file.name)
        dfs.append(df_temp)
        progresso.progress((i + 1) / len(uploaded_files), text=f"Lendo {file.name}...")
    
    progresso.empty()
    
    if not dfs:
        st.error("Nenhum arquivo processado.")
        st.stop()
        
    df_raw = pd.concat(dfs, ignore_index=True)
    
    if df_raw.empty:
        st.warning("Nenhum dado válido encontrado. Verifique o layout dos arquivos.")
        st.stop()

    # --- Sidebar: Filtros Globais ---
    with st.sidebar:
        st.header("🔍 Filtros")
        
        opts_empresa = sorted(df_raw['Empresa'].unique())
        sel_empresas = st.multiselect("Empresas", opts_empresa, default=opts_empresa)
        
        opts_comp = sorted(df_raw['Competência'].unique())
        sel_comp = st.multiselect("Mês/Competência", opts_comp, default=opts_comp)
        
        opts_cargo = sorted(df_raw['Cargo'].unique())
        sel_cargos = st.multiselect("Cargos", opts_cargo, default=opts_cargo)
        
        opts_evento = sorted(df_raw['Tipo de Evento'].unique())
        sel_eventos = st.multiselect("Eventos", opts_evento, default=opts_evento)

    # Aplica Filtros
    df = df_raw[
        (df_raw['Empresa'].isin(sel_empresas)) &
        (df_raw['Competência'].isin(sel_comp)) &
        (df_raw['Cargo'].isin(sel_cargos)) &
        (df_raw['Tipo de Evento'].isin(sel_eventos))
    ]
    
    if df.empty:
        st.info("Nenhum dado para exibir com os filtros atuais.")
        st.stop()

    # --- KPIs ---
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    
    total_custo = df['Valor (R$)'].sum()
    total_horas = df['Horas Decimais'].sum()
    qtd_colab = df['ID Func'].nunique()
    media = total_custo / qtd_colab if qtd_colab else 0
    
    col1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("⏱️ Total Horas", f"{total_horas:,.1f} h")
    col3.metric("👥 Colaboradores", qtd_colab)
    col4.metric("📊 Ticket Médio", f"R$ {media:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- Abas Estratégicas ---
    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏢 Visão Geral", 
        "🆚 Comparativo CNPJ", 
        "🧠 Inteligência (Outliers)", 
        "📄 Dados Detalhados"
    ])

    # 1. Visão Geral
    with tab1:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Custos por Tipo de Evento")
            fig_bar = px.bar(
                df.groupby('Tipo de Evento')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=True),
                x='Valor (R$)', y='Tipo de Evento', orientation='h', text_auto='.2s',
                title="Distribuição de Valores"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c2:
            st.subheader("Top Cargos")
            df_pie = df.groupby('Cargo')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)', ascending=False).head(7)
            fig_pie = px.pie(df_pie, values='Valor (R$)', names='Cargo', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    # 2. Comparativo
    with tab2:
        if len(sel_empresas) > 1:
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                df_total_emp = df.groupby('Empresa')['Valor (R$)'].sum().reset_index()
                fig_comp1 = px.bar(df_total_emp, x='Empresa', y='Valor (R$)', color='Empresa', title="Custo Total por Empresa", text_auto='.2s')
                st.plotly_chart(fig_comp1, use_container_width=True)
            with col_comp2:
                df_avg = df.groupby('Empresa').agg({'Valor (R$)': 'sum', 'ID Func': 'nunique'}).reset_index()
                df_avg['Media'] = df_avg['Valor (R$)'] / df_avg['ID Func']
                fig_comp2 = px.bar(df_avg, x='Empresa', y='Media', color='Empresa', title="Custo Médio por Colaborador", text_auto='.2f')
                st.plotly_chart(fig_comp2, use_container_width=True)
        else:
            st.info("Selecione mais de uma empresa na barra lateral para ativar o modo comparativo.")

    # 3. Inteligência (Outliers)
    with tab3:
        st.markdown("### 🚨 Detecção de Anomalias")
        col_out1, col_out2 = st.columns([1, 3])
        with col_out1:
            limite_horas = st.number_input("Limite de Horas", value=100, step=10)
            limite_valor = st.number_input("Limite de Valor (R$)", value=5000.0, step=500.0)
            
        with col_out2:
            df_func = df.groupby(['Nome', 'Empresa', 'Cargo']).agg({
                'Horas Decimais': 'sum',
                'Valor (R$)': 'sum'
            }).reset_index()
            outliers = df_func[
                (df_func['Horas Decimais'] > limite_horas) | 
                (df_func['Valor (R$)'] > limite_valor)
            ].sort_values('Valor (R$)', ascending=False)
            
            if not outliers.empty:
                st.warning(f"{len(outliers)} colaboradores encontrados acima dos limites.")
                outliers_display = outliers.copy()
                outliers_display['Valor (R$)'] = outliers_display['Valor (R$)'].apply(lambda x: f"R$ {x:,.2f}")
                outliers_display['Horas Decimais'] = outliers_display['Horas Decimais'].apply(lambda x: f"{x:.2f}")
                st.dataframe(outliers_display, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhum colaborador ultrapassou os limites.")

    # 4. Dados Detalhados (COM A LÓGICA NOVA)
    with tab4:
        st.markdown("### 📑 Tabela Detalhada por Funcionário")
        
        # 1. Categorizar Eventos (60%, DSR ou Outros)
        def categorizar_evento(evento):
            evt = str(evento).upper()
            if "60%" in evt: return "60%"
            if "DSR" in evt: return "DSR"
            return "OUTROS"
            
        df['Categoria_Temp'] = df['Tipo de Evento'].apply(categorizar_evento)
        
        # 2. Pivotar (Transformar linhas em colunas)
        pivot_df = df.pivot_table(
            index=['Empresa', 'Competência', 'ID Func', 'Nome', 'Cargo'],
            columns='Categoria_Temp',
            values=['Horas Decimais', 'Valor (R$)'],
            aggfunc='sum',
            fill_value=0
        )
        
        # 3. Achatamento das colunas MultiIndex
        pivot_df.columns = [f'{col[0]}|{col[1]}' for col in pivot_df.columns]
        pivot_df = pivot_df.reset_index()
        
        # 4. Garantir que as colunas existam (caso não tenha nenhum DSR no filtro, por exemplo)
        cols_esperadas = [
            'Horas Decimais|60%', 'Valor (R$)|60%', 
            'Horas Decimais|DSR', 'Valor (R$)|DSR'
        ]
        for col in cols_esperadas:
            if col not in pivot_df.columns:
                pivot_df[col] = 0.0

        # 5. Criar Coluna Total Geral
        pivot_df['Total Geral (R$)'] = pivot_df['Valor (R$)|60%'] + pivot_df['Valor (R$)|DSR']
        
        # Se houver categoria "OUTROS", somar também
        if 'Valor (R$)|OUTROS' in pivot_df.columns:
             pivot_df['Total Geral (R$)'] += pivot_df['Valor (R$)|OUTROS']

        # 6. Renomear e Organizar para Exibição Final
        df_final = pivot_df.copy()
        
        # Converter horas decimais para string HH:MM para a coluna visual (opcional, mas solicitado "Banco de Hora")
        df_final['Banco de Hora 60%'] = df_final['Horas Decimais|60%'].apply(formatar_horas_decimal_para_str)
        df_final['Horas DSR'] = df_final['Horas Decimais|DSR'].apply(formatar_horas_decimal_para_str)
        
        # Selecionar colunas finais
        colunas_finais = [
            'Empresa', 'Competência', 'Nome', 'Cargo',
            'Banco de Hora 60%', 'Valor (R$)|60%',
            'Horas DSR', 'Valor (R$)|DSR',
            'Total Geral (R$)'
        ]
        
        df_exibicao = df_final[colunas_finais].copy()
        
        # Renomear para ficar bonito no header
        df_exibicao.columns = [
            'Empresa', 'Competência', 'Nome', 'Cargo',
            'Banco de Hora 60%', 'Valor 60% (R$)',
            'Horas DSR', 'Valor DSR (R$)',
            'Total Geral (R$)'
        ]
        
        # Formatação de Moeda
        colunas_valor = ['Valor 60% (R$)', 'Valor DSR (R$)', 'Total Geral (R$)']
        for col in colunas_valor:
            df_exibicao[col] = df_exibicao[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
        
        # Download
        csv_buffer = df_exibicao.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar Planilha Consolidada (Excel/CSV)",
            data=csv_buffer,
            file_name="relatorio_consolidado_folha.csv",
            mime="text/csv"
        )

else:
    st.info("Aguardando upload dos arquivos CSV...")
    st.markdown("""
        **Instruções:**
        1. Clique em 'Browse files' acima.
        2. Selecione todos os arquivos CSV (ex: BD, Matias, Candeias).
        3. O sistema identificará automaticamente as empresas e gerará o dashboard.
    """)
