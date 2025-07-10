import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth

# Esta função garante que o Firebase seja inicializado apenas uma vez.
def initialize_firebase():
    """
    Inicializa a conexão com o Firebase usando as credenciais do Streamlit Secrets,
    garantindo que o objeto de credenciais seja um dicionário Python válido.
    """
    try:
        # Verifica se o app já foi inicializado para evitar erros
        firebase_admin.get_app()
    except ValueError:
        try:
            # **A CORREÇÃO ESTÁ AQUI**
            # Convertemos explicitamente o objeto de segredos para um dicionário
            firebase_creds_dict = dict(st.secrets["firebase_credentials"])

            # Verificação para garantir que as credenciais foram carregadas
            if not firebase_creds_dict:
                st.error("As credenciais do Firebase não foram carregadas dos segredos. Verifique o arquivo secrets.toml.")
                st.stop()

            cred = credentials.Certificate(firebase_creds_dict)
            
            firebase_admin.initialize_app(cred, {
                'storageBucket': firebase_creds_dict.get("storage_bucket_url")
            })
        except Exception as e:
            # Mostra uma mensagem de erro mais clara se algo falhar
            st.error(f"Erro na inicialização do Firebase: {e}")
            st.info("Verifique se a formatação do seu arquivo .streamlit/secrets.toml está correta, especialmente a 'private_key' com aspas triplas.")
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
        # Evita que um erro de log quebre a aplicação inteira
        print(f"Erro ao registrar log: {e}")
