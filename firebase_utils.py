import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth

# Esta função garante que o Firebase seja inicializado apenas uma vez.
def initialize_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        try:
            firebase_creds_dict = st.secrets["firebase_credentials"]
            cred = credentials.Certificate(firebase_creds_dict)
            firebase_admin.initialize_app(cred, {
                'storageBucket': firebase_creds_dict["storage_bucket_url"]
            })
        except Exception as e:
            st.error(f"Erro na inicialização do Firebase: {e}")
            st.stop()

# Inicializa o app ao carregar o módulo
initialize_firebase()

# Referências para os serviços que serão usados em outras páginas
db = firestore.client()
bucket = storage.bucket()

# Função de log (permanece a mesma)
def log_activity(user_email, action, details=""):
    try:
        log_data = {
            "user_email": user_email,
            "action": action,
            "details": details,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection("logs").add(log_data)
    except Exception as e:
        print(f"Erro ao registrar log: {e}")
