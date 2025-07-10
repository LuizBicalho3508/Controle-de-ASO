import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import smtplib # Ou use uma API como SendGrid

def check_asos_expiration(request):
    # Inicializa o app dentro da função
    firebase_admin.initialize_app()
    db = firestore.client()

    # Lógica para encontrar ASOs vencendo
    hoje = datetime.now()
    limite_60_dias = hoje + timedelta(days=60)

    asos_vencendo = db.collection('asos').where('data_vencimento', '<=', limite_60_dias).stream()

    corpo_email = "Relatório de ASOs com vencimento próximo:\n\n"
    for aso in asos_vencendo:
        dados = aso.to_dict()
        vencimento_str = dados['data_vencimento'].strftime('%d/%m/%Y')
        corpo_email += f"- {dados['nome_funcionario']}, Vence em: {vencimento_str}\n"

    # Lógica de envio de email (exemplo com smtplib)
    # Substitua com seus dados de servidor de email
    # ... código para enviar o `corpo_email` para o email do admin ...

    return 'Verificação concluída.', 200
