import streamlit as st
import pandas as pd
from firebase_utils import db
from datetime import datetime

# --- Verificação de Login ---
if not st.session_state.get("authentication_status"):
    st.error("Você precisa estar logado para acessar esta página.")
    st.stop()

# --- Configurações da Página ---
st.logo("logobd.png")
st.title("Histórico de ASO por Funcionário")

# --- Função para carregar nomes únicos de funcionários ---
@st.cache_data(ttl=60)
def carregar_funcionarios():
    docs = db.collection("asos").stream()
    # Usar um set para garantir nomes únicos e depois converter para lista ordenada
    nomes = sorted(list(set(doc.to_dict().get('nome_funcionario') for doc in docs if doc.to_dict().get('nome_funcionario'))))
    return nomes

# --- Interface ---
funcionarios = carregar_funcionarios()
if not funcionarios:
    st.warning("Nenhum funcionário com ASO encontrado.")
    st.stop()

funcionario_selecionado = st.selectbox(
    "Selecione um funcionário para ver o histórico",
    options=funcionarios,
    index=None,
    placeholder="Digite ou selecione um nome..."
)

if funcionario_selecionado:
    st.subheader(f"Histórico de: {funcionario_selecionado}")
    
    # Busca todos os ASOs para o funcionário selecionado, ordenados pela data do exame
    docs = db.collection('asos').where('nome_funcionario', '==', funcionario_selecionado).order_by('data_exame', direction='DESCENDING').stream()
    
    historico = list(docs) # Converte o iterador para uma lista para verificar se está vazia

    if not historico:
        st.info("Nenhum ASO encontrado para este funcionário.")
    else:
        for aso_doc in historico:
            aso = aso_doc.to_dict()
            with st.container(border=True):
                col1, col2 = st.columns(2)
                
                data_exame = aso.get('data_exame')
                if isinstance(data_exame, datetime):
                    data_exame = data_exame.strftime('%d/%m/%Y')

                col1.write(f"**Tipo de Exame:** {aso.get('tipo_exame', 'N/A')}")
                col1.write(f"**Data do Exame:** {data_exame}")
                
                resultado_cor = "green" if aso.get('resultado') == "Apto" else "red"
                col2.write(f"**Resultado:** :{resultado_cor}[{aso.get('resultado', 'N/A')}]")
                col2.write(f"**Médico:** {aso.get('nome_medico', 'N/A')}")

                # Seção para mostrar os anexos
                if 'anexos' in aso and aso['anexos']:
                    with st.expander("Ver Anexos"):
                        for anexo_url in aso['anexos']:
                            # Extrai um nome de arquivo mais amigável da URL
                            try:
                                file_name = anexo_url.split('%2F')[-1].split('?')[0].replace('%20', ' ')
                            except:
                                file_name = "Link do Anexo"
                            st.link_button(f"Baixar {file_name}", anexo_url)
                # Compatibilidade com o campo antigo 'url_arquivo_aso'
                elif 'url_arquivo_aso' in aso and aso['url_arquivo_aso']:
                     with st.expander("Ver Anexo"):
                        st.link_button("Baixar ASO", aso['url_arquivo_aso'])

