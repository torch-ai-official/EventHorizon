# telegram_sender.py
# v2 — Sinais quantitativos com EV, confluência e regime
import datetime
import requests

CANAL_VIP_PT = "-1004322239279"
CANAL_VIP_EN = "-5434201315"


# ─────────────────────────────────────────────────────────────
# FORMATADORES
# ─────────────────────────────────────────────────────────────

def _barra_acuracia(acuracia: float) -> str:
    """Barra visual de 10 blocos para acurácia."""
    filled = round(acuracia / 10)
    return "█" * filled + "░" * (10 - filled)


def _emoji_ev(ev: float) -> str:
    if ev >= 0.15:
        return "🔥🔥"
    if ev >= 0.08:
        return "🔥"
    if ev >= 0.04:
        return "✅"
    return "⚠️"


def _label_confluencia(n: int) -> str:
    if n >= 4:
        return "MUITO FORTE ████"
    if n >= 3:
        return "FORTE ███░"
    if n >= 2:
        return "MODERADA ██░░"
    return "FRACA █░░░"


def formatar_sinal_pt(dados_sinal: dict) -> str:
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    direcao = dados_sinal["direcao"].upper()
    eh_alta = direcao in ("ALTA", "LONG", "BUY")

    cabecalho = "🚨 SINAL DE ALTA 📈" if eh_alta else "🚨 SINAL DE BAIXA 📉"
    emoji_ev  = _emoji_ev(dados_sinal.get("ev", 0))
    barra     = _barra_acuracia(dados_sinal["acuracia"])
    confluencia_label = _label_confluencia(dados_sinal.get("confluencia_n", 1))

    # Risco/retorno
    entrada = dados_sinal["entrada"]
    alvo    = dados_sinal["alvo"]
    stop    = dados_sinal["stop"]
    risco   = abs(entrada - stop)
    ganho   = abs(alvo    - entrada)
    rr      = round(ganho / risco, 2) if risco > 0 else 0

    # Regime
    regime_map = {
        "trend_up":   "📈 Tendência de Alta",
        "trend_down": "📉 Tendência de Baixa",
        "volatile":   "⚡ Volátil",
        "ranging":    "↔️  Lateralizado",
    }
    regime_str = regime_map.get(dados_sinal.get("regime", ""), "—")

    # Horizontes confirmadores
    horizontes_conf = dados_sinal.get("horizontes_confirmadores", [])
    h_str = "  ".join(f"`{h}`" for h in horizontes_conf) if horizontes_conf else "—"

    linhas = [
        f"{cabecalho}",
        f"",
        f"*Par:* `{dados_sinal['ativo'].upper()}` — *{dados_sinal['horizonte']}*",
        f"*Horário:* {agora}",
        f"",
        f"*Entrada:* `{entrada:.4f}`",
        f"*Alvo:*    `{alvo:.4f}`  _(+{ganho/entrada*100:.2f}%)_",
        f"*Stop:*    `{stop:.4f}`  _(-{risco/entrada*100:.2f}%)_",
        f"*R/R:*     `1:{rr}`",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Acurácia Histórica*",
        f"`{barra}` {dados_sinal['acuracia']:.1f}%",
        f"",
        f"{emoji_ev} *EV por operação:* `{dados_sinal.get('ev', 0)*100:+.2f}%`",
        f"📈 *Profit Factor:* `{dados_sinal['profit_factor']:.2f}`",
        f"🎯 *Confluência:* {confluencia_label}",
        f"🕐 *Horizontes conf.:* {h_str}",
        f"🌐 *Regime:* {regime_str}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🔗 [Auditoria Pública](https://torch-ai-official.github.io/trader-ai/dashboard.html)",
    ]
    return "\n".join(linhas)


def formatar_sinal_en(dados_sinal: dict) -> str:
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    direcao = dados_sinal["direcao"].upper()
    eh_alta = direcao in ("ALTA", "LONG", "BUY")

    cabecalho = "🚨 BUY SIGNAL 📈" if eh_alta else "🚨 SELL SIGNAL 📉"
    emoji_ev  = _emoji_ev(dados_sinal.get("ev", 0))
    barra     = _barra_acuracia(dados_sinal["acuracia"])
    confluencia_label = _label_confluencia(dados_sinal.get("confluencia_n", 1))

    entrada = dados_sinal["entrada"]
    alvo    = dados_sinal["alvo"]
    stop    = dados_sinal["stop"]
    risco   = abs(entrada - stop)
    ganho   = abs(alvo    - entrada)
    rr      = round(ganho / risco, 2) if risco > 0 else 0

    regime_map = {
        "trend_up":   "📈 Uptrend",
        "trend_down": "📉 Downtrend",
        "volatile":   "⚡ Volatile",
        "ranging":    "↔️  Ranging",
    }
    regime_str = regime_map.get(dados_sinal.get("regime", ""), "—")

    horizontes_conf = dados_sinal.get("horizontes_confirmadores", [])
    h_str = "  ".join(f"`{h}`" for h in horizontes_conf) if horizontes_conf else "—"

    linhas = [
        f"{cabecalho}",
        f"",
        f"*Pair:* `{dados_sinal['ativo'].upper()}` — *{dados_sinal['horizonte']}*",
        f"*Time:* {agora} (UTC-3)",
        f"",
        f"*Entry:*  `{entrada:.4f}`",
        f"*Target:* `{alvo:.4f}`  _(+{ganho/entrada*100:.2f}%)_",
        f"*Stop:*   `{stop:.4f}`  _(-{risco/entrada*100:.2f}%)_",
        f"*R/R:*    `1:{rr}`",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Historical Accuracy*",
        f"`{barra}` {dados_sinal['acuracia']:.1f}%",
        f"",
        f"{emoji_ev} *EV per trade:* `{dados_sinal.get('ev', 0)*100:+.2f}%`",
        f"📈 *Profit Factor:* `{dados_sinal['profit_factor']:.2f}`",
        f"🎯 *Confluence:* {confluencia_label}",
        f"🕐 *Confirming TFs:* {h_str}",
        f"🌐 *Regime:* {regime_str}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🔗 [Public Audit](https://torch-ai-official.github.io/trader-ai/dashboard-en.html)",
    ]
    return "\n".join(linhas)


def enviar_sinal_telegram(token_bot: str, chat_id: str, texto: str) -> bool:
    url = f"https://api.telegram.org/bot{token_bot}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       texto,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[Telegram] ✅ Enviado para {chat_id}")
            return True
        print(f"[Telegram] ❌ {r.status_code} — {r.text[:120]}")
        return False
    except Exception as e:
        print(f"[Telegram] Falha: {e}")
        return False


def enviar_para_todos_canais(token_bot: str, dados_sinal: dict):
    enviar_sinal_telegram(token_bot, CANAL_VIP_PT, formatar_sinal_pt(dados_sinal))
    enviar_sinal_telegram(token_bot, CANAL_VIP_EN, formatar_sinal_en(dados_sinal))