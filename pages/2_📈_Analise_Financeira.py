import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Análise Financeira", page_icon="📈", layout="wide")

# --- Verificação de Login (Padrão do seu projeto) ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Título e Logo ---
# Tenta carregar o logo se existir, senão segue sem erro
try:
    st.logo("logobd.png")
except:
    pass

st.title("📈 Dashboard de Análise de Folha/Extras")
st.markdown("Faça o upload dos relatórios CSV (Ficha Financeira) para gerar indicadores estratégicos.")

# --- Funções Auxiliares de Tratamento de Dados ---

def converter_valor_monetario(valor_str):
    """Converte string '1.234,56' para float 1234.56"""
    if pd.isna(valor_str): return 0.0
    try:
        # Remove pontos de milhar e troca vírgula decimal por ponto
        limpo = str(valor_str).replace('.', '').replace(',', '.')
        return float(limpo)
    except:
        return 0.0

def converter_horas(hora_str):
    """Converte string '123:30 hs' para float de horas decimais"""
    if pd.isna(hora_str): return 0.0
    try:
        # Remove ' hs' e espaços
        limpo = str(hora_str).lower().replace('hs', '').strip()
        partes = limpo.split(':')
        horas = int(partes[0])
        minutos = int(partes[1])
        return horas + (minutos / 60)
    except:
        return 0.0

def processar_csv_financeiro(uploaded_file):
    """
    Lê o CSV linha por linha para lidar com a estrutura de seções (Eventos)
    específica dos relatórios fornecidos.
    """
    stringio = io.StringIO(uploaded_file.getvalue().decode("latin-1")) # Encoding comum para esses sistemas
    
    dados = []
    evento_atual = None
    
    for linha in stringio:
        linha = linha.strip()
        
        # Ignora linhas vazias ou separadores
        if not linha or linha.startswith('_'):
            continue
            
        # Identifica mudança de Evento (ex: "Evento: 37 Horas Extras 60%")
        if linha.startswith('"Evento:'):
            evento_atual = linha.replace('"Evento:', '').replace('"', '').strip()
            continue
            
        # Ignora linhas de cabeçalho repetidas ou totais
        if "Total do Evento" in linha or "Total da Empresa" in linha or "Relação de Eventos" in linha:
            continue
            
        partes = linha.split(';')
        
        # Validação simples: linhas de dados geralmente começam com um ID numérico (Func)
        # e têm pelo menos 6 colunas baseadas no padrão visto
        if len(partes) >= 6 and partes[0].replace('"', '').isdigit():
            try:
                # Extração baseada na estrutura: Func;Nome;Cargo_ID;Cargo_Nome;Situação;Referência;Valor
                # Ajustando indices conforme o CSV padrão fornecido
                # O CSV parece ter aspas em tudo, então removemos
                
                func_id = partes[0].replace('"', '')
                nome = partes[1].replace('"', '')
                # As colunas de cargo as vezes vem separadas ou juntas, vamos pegar pelo indice reverso para garantir o valor
                valor_raw = partes[-1].replace('"', '')
                ref_raw = partes[-2].replace('"', '')
                situacao = partes[-3].replace('"', '')
                cargo_nome = partes[-4].replace('"', '') # Assumindo posição fixa
                
                # Se cargo_nome for numérico, pegamos o anterior (ajuste fino)
                if cargo_nome.replace('.','').isdigit():
                     cargo_nome = partes[2].replace('"', '') # Fallback

                dados.append({
                    'ID Func': func_id,
                    'Nome': nome,
                    'Cargo': cargo_nome,
                    'Situação': situacao,
                    'Referência Original': ref_raw,
                    'Horas Decimais': converter_horas(ref_raw),
                    'Valor (R$)': converter_valor_monetario(valor_raw),
                    'Tipo de Evento': evento_atual,
                    'Arquivo Fonte': uploaded_file.name
                })
            except Exception as e:
                # Em caso de erro numa linha específica, logamos mas continuamos
                print(f"Erro ao processar linha: {linha} | Erro: {e}")
                continue

    return pd.DataFrame(dados)

# --- Interface de Upload ---
uploaded_files = st.file_uploader(
    "Carregar CSVs (Relatórios de Eventos Acumulados)", 
    type=["csv"], 
    accept_multiple_files=True
)

if uploaded_files:
    dfs = []
    barra_progresso = st.progress(0, text="Processando arquivos...")
    
    for i, file in enumerate(uploaded_files):
        df_temp = processar_csv_financeiro(file)
        dfs.append(df_temp)
        barra_progresso.progress((i + 1) / len(uploaded_files), text=f"Lendo {file.name}...")
    
    barra_progresso.empty()
    
    if not dfs:
        st.warning("Nenhum dado válido encontrado nos arquivos.")
        st.stop()

    # Consolida todos os arquivos em um único DataFrame
    df_completo = pd.concat(dfs, ignore_index=True)

    if df_completo.empty:
        st.error("O arquivo foi lido, mas nenhuma linha de dados foi extraída. Verifique se o formato é compatível.")
        st.stop()

    st.success(f"Dados processados com sucesso! {len(df_completo)} registros carregados.")
    st.divider()

    # --- Filtros Interativos ---
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    eventos_unicos = df_completo['Tipo de Evento'].unique()
    cargos_unicos = df_completo['Cargo'].unique()
    
    filtro_evento = col_filtro1.multiselect("Filtrar por Evento", options=eventos_unicos, default=eventos_unicos)
    filtro_cargo = col_filtro2.multiselect("Filtrar por Cargo", options=cargos_unicos, default=cargos_unicos)
    
    df_filtered = df_completo[
        (df_completo['Tipo de Evento'].isin(filtro_evento)) &
        (df_completo['Cargo'].isin(filtro_cargo))
    ]

    # --- KPIs Estratégicos (Big Numbers) ---
    st.subheader("Indicadores Gerais")
    
    total_valor = df_filtered['Valor (R$)'].sum()
    total_horas = df_filtered['Horas Decimais'].sum()
    total_funcionarios = df_filtered['ID Func'].nunique()
    media_por_func = total_valor / total_funcionarios if total_funcionarios > 0 else 0
    
    # Tentativa de separar Hora Extra de DSR para KPI específico
    valor_dsr = df_filtered[df_filtered['Tipo de Evento'].str.contains("DSR", na=False, case=False)]['Valor (R$)'].sum()
    valor_he = total_valor - valor_dsr

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    kpi1.metric("Custo Total (R$)", f"R$ {total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    kpi2.metric("Total de Horas", f"{total_horas:,.1f} h")
    kpi3.metric("Funcionários Impactados", total_funcionarios)
    kpi4.metric("Ticket Médio por Func.", f"R$ {media_por_func:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- Gráficos para Tomada de Decisão ---
    st.divider()
    st.subheader("Análise Gráfica")

    tab1, tab2 = st.tabs(["💰 Ranking de Custos", "📊 Distribuição e Cargos"])

    with tab1:
        st.markdown("**Top 10 Funcionários com Maior Custo (Soma de todos os eventos)**")
        
        # Agrupa por funcionário e soma os valores
        df_ranking = df_filtered.groupby(['Nome', 'Cargo'])['Valor (R$)'].sum().reset_index()
        df_ranking = df_ranking.sort_values(by='Valor (R$)', ascending=False).head(10)
        
        # Ajuste para exibição no gráfico nativo do Streamlit
        st.bar_chart(
            df_ranking,
            x="Nome",
            y="Valor (R$)",
            color="Cargo",  # Colora por cargo para dar contexto visual
            use_container_width=True
        )

    with tab2:
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.markdown("**Custo por Tipo de Evento**")
            df_evento = df_filtered.groupby('Tipo de Evento')['Valor (R$)'].sum().reset_index()
            st.bar_chart(df_evento, x="Tipo de Evento", y="Valor (R$)", use_container_width=True)
            
        with col_graf2:
            st.markdown("**Top 10 Cargos com Maior Custo Total**")
            df_cargo = df_filtered.groupby('Cargo')['Valor (R$)'].sum().reset_index().sort_values(by='Valor (R$)', ascending=False).head(10)
            st.bar_chart(df_cargo, x="Cargo", y="Valor (R$)", use_container_width=True, horizontal=True)

    # --- Dados Detalhados (Tabela) ---
    st.divider()
    with st.expander("🔎 Visualizar Dados Brutos Detalhados", expanded=False):
        # Formata colunas para exibição amigável
        df_display = df_filtered.copy()
        df_display['Valor (R$)'] = df_display['Valor (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df_display['Horas Decimais'] = df_display['Horas Decimais'].apply(lambda x: f"{x:.2f}")
        
        st.dataframe(
            df_display[['Nome', 'Cargo', 'Tipo de Evento', 'Referência Original', 'Valor (R$)', 'Situação']],
            use_container_width=True,
            hide_index=True
        )

else:
    # Estado inicial (sem arquivo)
    st.info("Aguardando upload de arquivos CSV para iniciar a análise.")
