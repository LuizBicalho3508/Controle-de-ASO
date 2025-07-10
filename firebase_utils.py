import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
import pyrebase

# --- INICIALIZAÇÃO DO FIREBASE ADMIN SDK ---
# Usado para operações de backend seguras (acesso ao Firestore, gerenciamento de usuários)

# Carrega as credenciais a partir dos secrets do Streamlit
# O st.secrets é um dicionário, então acessamos a chave "firebase_credentials"
firebase_creds_dict = st.secrets["firebase_credentials"]

try:
    # Verifica se já foi inicializado
    firebase_admin.get_app()
except ValueError:
    # Inicializa o app com as credenciais
    cred = credentials.Certificate(firebase_creds_dict)
    firebase_admin.initialize_app(cred, {
        'storageBucket': firebase_creds_dict["storage_bucket_url"] # Adicione a URL do seu bucket no JSON de secrets
    })

# Referências para os serviços
db = firestore.client()
bucket = storage.bucket()

# --- INICIALIZAÇÃO DO PYREBASE ---
# Usado para operações de autenticação do lado do cliente (login)
# As configurações do Pyrebase são diferentes das do Admin SDK
firebase_config = st.secrets["firebase_config"] # Crie essa seção nos seus secrets
firebase = pyrebase.initialize_app(firebase_config)
pyrebase_auth = firebase.auth()


# --- FUNÇÃO DE LOG ---
def log_activity(user_email, action, details=""):
    """Registra uma atividade no Firestore."""
    log_data = {
        "user_email": user_email,
        "action": action,
        "details": details,
        "timestamp": firestore.SERVER_TIMESTAMP # Usa o timestamp do servidor
    }
    db.collection("logs").add(log_data)
