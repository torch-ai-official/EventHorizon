# telegram_sender.py
import datetime
import requests

# IDs dos canais
CANAL_VIP_PT = "-1004322239279"
CANAL_VIP_EN = "-5434201315"

def formatar_sinal_pt(dados_sinal):
    """Formata o sinal em PORTUGUÊS"""
    agora = datetime.datetime.now().strftime("%H:%M:%S")

    emoji_direcao = "🚨 SINAL DE ALTA 📈"
    if dados_sinal["direcao"].upper() in ["BAIXA", "SHORT", "VENDA"]:
        emoji_direcao = "🚨 SINAL DE BAIXA 📉"

    template = (
        f"{emoji_direcao}\n"
        f"*Par:* {dados_sinal['ativo'].upper()} ({dados_sinal['horizonte']})\n"
        f"*Horário do Disparo:* {agora}\n\n"
        f"• *Entrada:* {dados_sinal['entrada']:.4f}\n"
        f"• *Alvo:* {dados_sinal['alvo']:.4f}\n"
        f"• *Stop Loss:* {dados_sinal['stop']:.4f}\n\n"
        f"📊 *Acurácia Histórica:* {dados_sinal['acuracia']:.1f}%\n"
        f"📈 *Profit Factor:* {dados_sinal['profit_factor']:.2f}\n\n"
        f"🔗 Auditoria: https://torch-ai-official.github.io/trader-ai/dashboard.html"
    )
    return template


def formatar_sinal_en(dados_sinal):
    """Formata o sinal em INGLÊS"""
    agora = datetime.datetime.now().strftime("%H:%M:%S")

    emoji = "🚨 BUY SIGNAL 📈" if dados_sinal["direcao"].upper() in ["ALTA", "LONG"] else "🚨 SELL SIGNAL 📉"

    template = (
        f"{emoji}\n"
        f"*Pair:* {dados_sinal['ativo'].upper()} ({dados_sinal['horizonte']})\n"
        f"*Time:* {agora} (UTC)\n\n"
        f"• *Entry:* {dados_sinal['entrada']:.4f}\n"
        f"• *Target:* {dados_sinal['alvo']:.4f}\n"
        f"• *Stop Loss:* {dados_sinal['stop']:.4f}\n\n"
        f"📊 *Historical Accuracy:* {dados_sinal['acuracia']:.1f}%\n"
        f"📈 *Profit Factor:* {dados_sinal['profit_factor']:.2f}\n\n"
        f"🔗 Public Audit: https://torch-ai-official.github.io/trader-ai/dashboard-en.html"
    )
    return template


def enviar_sinal_telegram(token_bot, chat_id, texto_formatado):
    """Envia sinal pro canal VIP via API do Telegram"""
    url = f"https://api.telegram.org/bot{token_bot}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto_formatado,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.datetime.now()}] Sinal enviado com sucesso para {chat_id}!")
            return True
        else:
            print(f"Erro ao enviar: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Falha na conexão com a API do Telegram: {e}")
        return False


def enviar_para_todos_canais(token_bot, dados_sinal):
    """Envia o sinal para TODOS os canais VIP"""
    msg_pt = formatar_sinal_pt(dados_sinal)
    msg_en = formatar_sinal_en(dados_sinal)
    
    enviar_sinal_telegram(token_bot, CANAL_VIP_PT, msg_pt)
    enviar_sinal_telegram(token_bot, CANAL_VIP_EN, msg_en)