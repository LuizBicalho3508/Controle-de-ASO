import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime, timedelta

# Importa a biblioteca para ler arquivos TOML.
# Tenta usar a nativa do Python 3.11+, se não der, usa a que instalamos.
try:
    import tomllib
except ModuleNotFoundError:
    import toml as tomllib


# --- CONFIGURAÇÕES ---
# O caminho padrão para o arquivo de segredos do Streamlit
SECRETS_FILE_PATH = ".streamlit/secrets.toml"
ADMIN_EMAIL = 'admin@suaempresa.com'
ADMIN_PASSWORD = 'SenhaForte123' # TROQUE POR UMA SENHA SEGURA

# --- NOVA LÓGICA PARA LER O SECRETS.TOML ---
print("--- Lendo arquivo de credenciais secrets.toml ---")
if not os.path.exists(SECRETS_FILE_PATH):
    print(f"❌ Erro: Arquivo de segredos não encontrado em '{SECRETS_FILE_PATH}'")
    print("   Certifique-se de que o arquivo .streamlit/secrets.toml existe e está preenchido.")
    exit()

try:
    with open(SECRETS_FILE_PATH, "rb") as f:
        secrets = tomllib.load(f)
    
    # Pega a seção específica das credenciais do Firebase
    firebase_credentials = secrets.get("firebase_credentials")
    if not firebase_credentials:
        raise ValueError("A seção [firebase_credentials] não foi encontrada no secrets.toml")

except Exception as e:
    print(f"❌ Erro ao ler ou processar o arquivo secrets.toml: {e}")
    exit()


# --- INICIALIZAÇÃO DO FIREBASE ---
try:
    # Carrega as credenciais a partir do dicionário lido do TOML
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
    print("✅ Conexão com o Firebase bem-sucedida.")
except Exception as e:
    print(f"❌ Erro ao conectar com o Firebase: {e}")
    print("   Verifique se a seção [firebase_credentials] no seu secrets.toml está correta.")
    exit()

db = firestore.client()

# --- 1. CRIAÇÃO DO USUÁRIO ADMIN (lógica inalterada) ---
print("\n--- Iniciando criação do usuário admin ---")
try:
    user = auth.create_user(
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        email_verified=True,
        display_name='Administrador'
    )
    auth.set_custom_user_claims(user.uid, {'role': 'admin'})
    print(f"✅ Usuário admin '{ADMIN_EMAIL}' criado com sucesso!")

except auth.EmailAlreadyExistsError:
    print(f"⚠️  O usuário admin '{ADMIN_EMAIL}' já existe. Nenhuma ação foi tomada.")
except Exception as e:
    print(f"❌ Erro ao criar usuário admin: {e}")


# --- 2. CRIAÇÃO DE UM ASO DE EXEMPLO (lógica inalterada) ---
print("\n--- Iniciando criação de ASO de exemplo ---")
try:
    asos_ref = db.collection('asos').where('nome_funcionario', '==', 'Funcionário Exemplo').limit(1).stream()
    if not any(asos_ref):
        data_exame_exemplo = datetime.now() - timedelta(days=200)
        data_vencimento_exemplo = datetime.now() + timedelta(days=55)

        aso_data = {
            "nome_funcionario": "Funcionário Exemplo",
            "funcao": "Desenvolvedor",
            "tipo_exame": "Periódico",
            "resultado": "Apto",
            "data_exame": data_exame_exemplo,
            "data_vencimento": data_vencimento_exemplo,
            "nome_medico": "Dra. Grey",
            "crm_medico": "98765-BR",
            "url_arquivo_aso": None,
            "lancado_por": "script_seed",
            "data_lancamento": firestore.SERVER_TIMESTAMP
        }
        
        db.collection('asos').add(aso_data)
        print("✅ ASO de exemplo para 'Funcionário Exemplo' criado com sucesso.")
    else:
        print("⚠️  ASO de exemplo já existe. Nenhuma ação foi tomada.")

except Exception as e:
    print(f"❌ Erro ao criar ASO de exemplo: {e}")

print("\n🚀 Estrutura inicial do banco de dados configurada!")
