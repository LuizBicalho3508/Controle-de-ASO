import streamlit as st
import pandas as pd
from firebase_utils import db

if st.session_state.get("role") != "admin":
    st.error("Acesso negado.")
    st.stop()

st.title("Logs de Atividade do Sistema")

@st.cache_data(ttl=60)
def carregar_logs():
    logs_ref = db.collection("logs").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    logs = [doc.to_dict() for doc in logs_ref]
    return pd.DataFrame(logs)

df_logs = carregar_logs()
st.dataframe(df_logs, use_container_width=True)
