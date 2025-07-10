import os
import firebase_admin
from firebase_admin import credentials, auth

# Tenta usar a biblioteca TOML nativa do Python 3.11+, se não, usa a instalada
try:
    import tomllib
except ModuleNotFoundError:
    import toml as tomllib

# --- DADOS DO USUÁRIO ADMIN ---
ADMIN_EMAIL = "iasminmeloadm@gmail.com"
ADMIN_PASSWORD = "Senh@123"

# --- LÓGICA DE CONEXÃO E CRIAÇÃO ---

SECRETS_FILE_PATH = ".streamlit/secrets.toml"

print("--- Iniciando script de criação de administrador ---")

# 1. Carregar credenciais do arquivo secrets.toml
print(f"Lendo credenciais do arquivo: {SECRETS_FILE_PATH}")
if not os.path.exists(SECRETS_FILE_PATH):
    print(f"❌ ERRO: Arquivo de segredos não encontrado em '{SECRETS_FILE_PATH}'.")
    print("   Por favor, crie e preencha o arquivo .streamlit/secrets.toml antes de continuar.")
    exit()

try:
    with open(SECRETS_FILE_PATH, "rb") as f:
        secrets = tomllib.load(f)
    firebase_credentials = secrets.get("firebase_credentials")
    if not firebase_credentials:
        raise ValueError("A seção [firebase_credentials] não foi encontrada no secrets.toml")
except Exception as e:
    print(f"❌ ERRO ao ler o arquivo secrets.toml: {e}")
    exit()

# 2. Inicializar o Firebase Admin SDK
try:
    cred = credentials.Certificate(firebase_credentials)
    # Evita erro caso o script seja executado múltiplas vezes em um mesmo processo
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    print("✅ Conexão com o Firebase estabelecida.")
except Exception as e:
    print(f"❌ ERRO ao inicializar o Firebase: {e}")
    exit()

# 3. Criar o usuário administrador no Firebase Authentication
print(f"Tentando criar o usuário '{ADMIN_EMAIL}'...")
try:
    # Cria o usuário com email e senha
    user = auth.create_user(
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        email_verified=True, # Marcar o e-mail como verificado
        display_name='Administrador Iasmin'
    )
    
    # Adiciona a permissão de "admin" ao usuário
    auth.set_custom_user_claims(user.uid, {'role': 'admin'})
    
    print("\n-----------------------------------------------------")
    print(f"✅ SUCESSO! Usuário administrador criado.")
    print(f"   Email: {user.email}")
    print(f"   UID: {user.uid}")
    print("   Permissão de 'admin' atribuída.")
    print("-----------------------------------------------------")

except auth.EmailAlreadyExistsError:
    print(f"⚠️  AVISO: O usuário com o email '{ADMIN_EMAIL}' já existe no Firebase.")
    print("   Nenhuma alteração foi feita. Se precisar redefinir a permissão ou senha, use o console do Firebase.")
except Exception as e:
    print(f"❌ ERRO inesperado durante a criação do usuário: {e}")
