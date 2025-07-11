import streamlit as st
import pandas as pd
from firebase_utils import db
from datetime import datetime, timezone
from fpdf import FPDF

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Configurações da Página ---
st.logo("logobd.png")
st.title("Gerador de Relatórios em PDF")

# --- Classe para gerar o PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Relatório de Vencimento de ASOs', 0, 1, 'C')
        self.set_font('Arial', '', 8)
        self.cell(0, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        # Usar encode/decode para lidar com caracteres especiais como acentos
        self.cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        for line in body:
            # Usar encode/decode para lidar com caracteres especiais como acentos
            self.multi_cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'))
        self.ln()

# --- Lógica da Página ---
st.info("Selecione os status dos ASOs que você deseja incluir no relatório PDF.")

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

    status_disponiveis = ['Vencido', 'Vence em até 30 dias', 'Vence em até 60 dias']
    status_selecionados = st.multiselect(
        "Selecione os Status para o Relatório",
        options=status_disponiveis,
        default=status_disponiveis
    )

    if st.button("Gerar Relatório PDF"):
        df_relatorio = df_asos[df_asos['Status'].isin(status_selecionados)]
        
        if df_relatorio.empty:
            st.warning("Nenhum ASO encontrado para os status selecionados.")
        else:
            pdf = PDF()
            pdf.add_page()
            
            for status in status_selecionados:
                df_status = df_relatorio[df_relatorio['Status'] == status]
                if not df_status.empty:
                    pdf.chapter_title(status)
                    lista_funcionarios = []
                    for _, row in df_status.iterrows():
                        venc_str = row['data_vencimento'].strftime('%d/%m/%Y')
                        linha = f"Funcionário: {row['nome_funcionario']} | Função: {row.get('funcao', 'N/A')} | Vencimento: {venc_str}"
                        lista_funcionarios.append(linha)
                    pdf.chapter_body(lista_funcionarios)

            # --- CORREÇÃO AQUI ---
            # Chamamos pdf.output() sem argumentos para obter os dados em formato de bytes,
            # que é o formato esperado pelo st.download_button.
            pdf_output = pdf.output()
            
            st.download_button(
                label="Baixar Relatório PDF",
                data=pdf_output,
                file_name=f"relatorio_asos_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
else:
    st.info("Nenhum ASO cadastrado no sistema.")
