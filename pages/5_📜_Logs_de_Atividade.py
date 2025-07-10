import streamlit as st
import pandas as pd
from firebase_utils import db
from google.cloud.firestore_v1.query import Query

if st.session_state.get("role") != "admin":
    st.error("Acesso negado. Esta página é restrita a administradores.")
    st.stop()

st.logo("logobd.png") # ADICIONADO AQUI
st.title("Logs de Atividade do Sistema")

@st.cache_data(ttl=60)
def carregar_logs():
    logs_ref = db.collection("logs").order_by("timestamp", direction=Query.DESCENDING).limit(200).stream()
    logs = []
    for doc in logs_ref:
        log_data = doc.to_dict()
        # Garante que o timestamp existe antes de formatar
        if 'timestamp' in log_data and log_data['timestamp']:
            log_data['timestamp'] = pd.to_datetime(log_data['timestamp']).strftime('%d/%m/%Y %H:%M:%S')
        else:
            log_data['timestamp'] = 'N/A'
        logs.append(log_data)

    if not logs:
        return pd.DataFrame()
    
    df = pd.DataFrame(logs)
    return df

df_logs = carregar_logs()
if not df_logs.empty:
    st.dataframe(df_logs, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum log de atividade registrado.")
