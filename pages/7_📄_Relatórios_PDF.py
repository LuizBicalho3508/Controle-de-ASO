import streamlit as st
import pandas as pd
from firebase_utils import db
from datetime import datetime, timezone
import io

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Configurações da Página ---
st.logo("logobd.png")
st.title("Gerador de Relatórios em Excel (XLSX)")

# --- Lógica da Página ---
st.info("Selecione os status dos ASOs que você deseja incluir no relatório.")

# Carrega os dados
docs = db.collection("asos").stream()
asos = [doc.to_dict() for doc in docs]
df_asos = pd.DataFrame(asos)

if not df_asos.empty:
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

    status_disponiveis = ['Vencido', 'Vence em até 30 dias', 'Vence em até 60 dias', 'Arquivado', 'Em dia']
    status_selecionados = st.multiselect(
        "Selecione os Status para o Relatório",
        options=status_disponiveis,
        default=['Vencido', 'Vence em até 30 dias', 'Vence em até 60 dias']
    )

    if st.button("Gerar Relatório XLSX"):
        df_relatorio = df_asos[df_asos['Status'].isin(status_selecionados)]
        
        if df_relatorio.empty:
            st.warning("Nenhum ASO encontrado para os status selecionados.")
        else:
            # Seleciona e renomeia as colunas para o relatório final
            colunas_exportar = {
                'nome_funcionario': 'Funcionário',
                'funcao': 'Função',
                'tipo_exame': 'Tipo de Exame',
                'resultado': 'Resultado',
                'data_exame': 'Data do Exame',
                'data_vencimento': 'Data de Vencimento',
                'Status': 'Status',
                'lancado_por': 'Lançado Por'
            }
            df_export = df_relatorio[list(colunas_exportar.keys())].copy()
            df_export.rename(columns=colunas_exportar, inplace=True)
            
            # Formata as colunas de data
            df_export['Data do Exame'] = pd.to_datetime(df_export['Data do Exame']).dt.strftime('%d/%m/%Y')
            df_export['Data de Vencimento'] = pd.to_datetime(df_export['Data de Vencimento']).dt.strftime('%d/%m/%Y')

            # Cria um buffer de bytes na memória para salvar o arquivo Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Relatório ASOs')
            
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Baixar Relatório XLSX",
                data=excel_data,
                file_name=f"relatorio_asos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Nenhum ASO cadastrado no sistema.")

