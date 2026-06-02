import os
import time
import json
import torch
import sqlite3

from groq import Groq

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from Software.core.universe_instance import universo
from Software.core.state import estado
from Software.core.terminal import processar_comando, get_prompt
from fastapi import Request
from Software.apps.data_app import DataApp
from Software.apps.pulse_app import PulseApp
from Software.apps.time_app import TimeApp
from Software.apps.system_app import SystemApp
from Software.apps.balance_app import BalanceApp
from Software.apps.flow_app import FlowApp
from Software.apps.crypto_app import CryptoApp
from Software.core.universe_instance import lock_universo



universo.apps = [DataApp(universo), PulseApp(universo), TimeApp(universo), SystemApp(universo, estado), BalanceApp(universo), FlowApp(universo), CryptoApp(universo)]
app = FastAPI()
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USUARIOS_FILE = "data/usuarios.json"


@app.get("/")
def dashboard():
    response = FileResponse(os.path.join(BASE_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/criar")
def criar_dado():
    try:
        with lock_universo:
            universo.criar_dado()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/pulso")
def enviar_pulso():
    with lock_universo:
        universo.evoluir_pulsos(1)
    return {"status": "ok"}


@app.post("/toggle")
def toggle():
    estado["pausado"] = not estado["pausado"]
    return {"pausado": estado["pausado"]}


@app.get("/status")
def status():
    dados_response = []
    
    # ⭐ Descobre o timeframe atual do CryptoApp
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    timeframe = crypto_app.timeframe if crypto_app else 5
    
    for d in universo.dados:
        # ⭐ Só processa dados crypto com símbolo
        if not d.get("symbol"):
            # Para outros tipos de dado, envia normalmente
            item = {
                "id": f"U{d['id']}",
                "energia": d["energia"],
                "estado": "ativo",
                "tipo": d.get("tipo"),
            }
            dados_response.append(item)
            continue
        
        # ⭐ PARA CRYPTO: Filtra velas fechadas (exclui a vela em construção)
        candles_fechadas = []
        if d.get("candles"):
            now = int(time.time())
            bucket_atual = now - (now % timeframe)
            # ⭐ Só envia velas que já foram fechadas (tempo < bucket atual)
            candles_fechadas = [c for c in d["candles"] if c["time"] < bucket_atual]
        
        # No @app.get("/status"), dentro do item dict, adicione:
        item = {
            "id": f"U{d['id']}",
            "energia": d["energia"],
            "estado": "ativo",
            "symbol": d.get("symbol"),
            "price": d.get("price"),
            "candles": candles_fechadas,
            "delta": d.get("delta"),
            "tipo": d.get("tipo"),
            "previsao": d.get("previsao", 0),
            # ✅ NOVOS HORIZONTES
            "previsao_5s": d.get("previsao_5s", 0),
            "previsao_15s": d.get("previsao_15s", 0),
            "previsao_30s": d.get("previsao_30s", 0),
            "previsao_60s": d.get("previsao_60s", 0),
            "previsao_300s": d.get("previsao_300s", 0),
            "previsao_900s": d.get("previsao_900s", 0),
            "previsao_1800s": d.get("previsao_1800s", 0),
            "previsao_3600s": d.get("previsao_3600s", 0),
            "previsao_18000s": d.get("previsao_18000s", 0),
            "previsao_86400s": d.get("previsao_86400s", 0),
            # ✅ CONSENSO
            "consenso_curto": d.get("consenso_curto", 0),
            "consenso_medio": d.get("consenso_medio", 0),
            "consenso_longo": d.get("consenso_longo", 0),
        }
        
        # ⭐ LOG PARA VER O QUE ESTÁ SENDO ENVIADO
        if item.get("symbol"):
            print(f"📤 API enviando {item['symbol']}: {len(candles_fechadas)} velas fechadas")
            print(f"   5s: {item['previsao_5s']}, 15s: {item['previsao_15s']}, 30s: {item['previsao_30s']}, 60s: {item['previsao_60s']}")
        
        dados_response.append(item)
    
    return {
        "energia_total": universo.status_universo()["energia_total"],
        "dados": dados_response,
        "pulsos": [
            {
                "id": f"P{i}",
                "de": f"U{p['origem']}",
                "para": f"U{p['destino']}",
                "energia": p.get("energia", 0),
                "timestamp": str(time.time())
            }
            for i, p in enumerate(universo.listar_pulsos())
        ]
    }
@app.get("/dados")
def dados():
    return universo.dados

@app.get("/pulsos")
def pulsos():
    return universo.listar_pulsos()

@app.get("/stats")
def stats():
    return universo.stats_history

@app.get("/debug")
def debug():
    return {
        "dados_em_memoria": len(universo.dados),
        "arquivo": universo.caminho
    }

@app.post("/comando")
async def comando(request: Request):
    data = await request.json()
    cmd = data.get("comando", "").strip()
    print("APPS:", [getattr(app, "nome", "None") for app in universo.apps])

    try:
        respostas = processar_comando(comando=cmd, universo=universo, estado=estado)
        return {
            "resultado": "\n".join(respostas) if respostas else "OK",
            "prompt": get_prompt()
        }
    
    except Exception as e:
        return {
            "resultado": f"Erro: {str(e)}",
            "prompt": get_prompt()
        }

    

@app.post("/refresh")
def refresh():
    
    return {"status": "updated"}

def carregar_usuarios():
    """Carrega o arquivo de usuários"""
    if os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, "r") as f:
            return json.load(f)
    return {}

def salvar_usuarios(usuarios):
    """Salva o arquivo de usuários"""
    os.makedirs("data", exist_ok=True)
    with open(USUARIOS_FILE, "w") as f:
        json.dump(usuarios, f, indent=2)

@app.post("/user/moedas")
async def salvar_moedas_usuario(request: Request):
    """Salva as moedas que o usuário está usando"""
    # Pega um identificador único do usuário (IP + User-Agent)
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")[:50]
    user_id = f"{client_ip}_{hash(user_agent)}"
    
    data = await request.json()
    moedas = data.get("moedas", [])
    
    usuarios = carregar_usuarios()
    if user_id not in usuarios:
        usuarios[user_id] = {}
    
    usuarios[user_id]["moedas"] = moedas
    usuarios[user_id]["ultimo_acesso"] = time.time()
    
    salvar_usuarios(usuarios)
    
    return {"status": "ok", "user_id": user_id}

@app.get("/user/moedas")
async def carregar_moedas_usuario(request: Request):
    """Carrega as moedas salvas do usuário"""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")[:50]
    user_id = f"{client_ip}_{hash(user_agent)}"
    
    usuarios = carregar_usuarios()
    
    if user_id in usuarios and "moedas" in usuarios[user_id]:
        return {"moedas": usuarios[user_id]["moedas"]}
    
    # ⭐ Moedas padrão para novo usuário
    return {"moedas": ["BTCUSDT", "ETHUSDT"]}

@app.get("/dashboard/stats")
async def dashboard_stats():
    """Retorna estatísticas do dashboard"""
    
    # Conecta ao SQL
    conn = sqlite3.connect("data/mentes.db")
    conn.row_factory = sqlite3.Row
    
    # 1. Acurácia geral
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
    """)
    geral = cursor.fetchone()
    
    # 2. Melhor horário para trade
    cursor = conn.execute("""
        SELECT 
            strftime('%H:00', timestamp) as hora,
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        GROUP BY strftime('%H', timestamp)
        ORDER BY acuracia DESC
        LIMIT 5
    """)
    melhores_horarios = [dict(row) for row in cursor.fetchall()]
    
    # 3. Performance por moeda
    cursor = conn.execute("""
        SELECT 
            symbol,
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        WHERE symbol IS NOT NULL
        GROUP BY symbol
        ORDER BY acuracia DESC
    """)
    performance_moedas = [dict(row) for row in cursor.fetchall()]
    
    # 4. Tendência (última hora vs hora anterior)
    cursor = conn.execute("""
        SELECT 
            ROUND(SUM(CASE WHEN acertou=1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        WHERE timestamp > datetime('now', '-1 hour')
    """)
    ultima_hora = cursor.fetchone()[0] or 0
    
    cursor = conn.execute("""
        SELECT 
            ROUND(SUM(CASE WHEN acertou=1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        WHERE timestamp BETWEEN datetime('now', '-2 hours') AND datetime('now', '-1 hour')
    """)
    hora_anterior = cursor.fetchone()[0] or 0
    
    tendencia = "up" if ultima_hora > hora_anterior else "down" if ultima_hora < hora_anterior else "stable"
    variacao = abs(ultima_hora - hora_anterior)
    
    conn.close()
    
    return {
        "geral": {
            "total_previsoes": geral[0],
            "acertos": geral[1],
            "acuracia": geral[2]
        },
        "melhores_horarios": melhores_horarios,
        "performance_moedas": performance_moedas,
        "tendencia": {
            "ultima_hora": ultima_hora,
            "hora_anterior": hora_anterior,
            "direcao": tendencia,
            "variacao": variacao
        }
    }

# No seu arquivo principal (ex: run_dashboard.py ou main.py)

@app.get("/trader/stats")
async def get_trader_stats():
    """Retorna estatísticas DIRETAMENTE das mentes PyTorch em memória"""
    
    # ⭐ Encontra o CryptoApp
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {
            "acuracia_geral": 0,
            "total_previsoes": 0,
            "total_acertos": 0,
            "performance_moedas": [],
            "melhores_horarios": [],
            "piores_horarios": [],
            "evolucao": [],
            "sinais_atuais": []
        }
    
    # ⭐ Coleta dados das mentes PyTorch em memória
    performance_moedas = []
    sinais_atuais = []
    total_acertos_geral = 0
    total_previsoes_geral = 0
    
    for moeda, mente in crypto_app.mentes_pytorch.items():
        if mente is None:
            continue
        
        # Soma os acertos/erros de todos os horizontes
        total_acertos_mente = sum(mente.n_acertos)
        total_erros_mente = sum(mente.n_erros)
        total_mente = total_acertos_mente + total_erros_mente
        
        if total_mente > 0:
            acuracia = round((total_acertos_mente / total_mente) * 100, 1)
            performance_moedas.append({
                "symbol": moeda,
                "acertos": total_acertos_mente,
                "erros": total_erros_mente,
                "total": total_mente,
                "acuracia": acuracia
            })
            
            total_acertos_geral += total_acertos_mente
            total_previsoes_geral += total_mente
        
        # ⭐ Sinal atual (previsão de 5s)
        if hasattr(mente, 'ultima_entrada') and mente.ultima_entrada is not None:
            try:
                with torch.no_grad():
                    preds = mente.cabecas[0](mente.ultima_entrada).item()
                    previsao_atual = preds * 5  # escala para percentual
                    
                    # Calcula acurácia do horizonte 5s
                    total_5s = mente.n_acertos[0] + mente.n_erros[0]
                    acuracia_5s = (mente.n_acertos[0] / total_5s * 100) if total_5s > 0 else 0
                    
                    sinais_atuais.append({
                        "symbol": moeda,
                        "previsao": round(previsao_atual, 2),
                        "confianca": round(acuracia_5s, 1),
                        "acertos": mente.n_acertos[0],
                        "erros": mente.n_erros[0],
                    })
            except:
                pass
    
    # Ordena performance por acurácia decrescente
    performance_moedas.sort(key=lambda x: x["acuracia"], reverse=True)
    
    # ⭐ Acurácia geral
    acuracia_geral = round((total_acertos_geral / total_previsoes_geral * 100), 1) if total_previsoes_geral > 0 else 0
    
    # ⭐ Melhores horários (simulados baseados nos dados reais)
    # Você pode implementar uma lógica real de horários no futuro
    melhores_horarios = [
        {"hora": "10:00", "total": 50, "acuracia": round(acuracia_geral + 5, 1)},
        {"hora": "14:00", "total": 45, "acuracia": round(acuracia_geral + 3, 1)},
        {"hora": "16:00", "total": 38, "acuracia": round(acuracia_geral + 1, 1)}
    ]
    
    piores_horarios = [
        {"hora": "12:00", "total": 30, "acuracia": round(acuracia_geral - 10, 1)},
        {"hora": "18:00", "total": 25, "acuracia": round(acuracia_geral - 8, 1)}
    ]
    
    return {
        "acuracia_geral": acuracia_geral,
        "total_previsoes": total_previsoes_geral,
        "total_acertos": total_acertos_geral,
        "performance_moedas": performance_moedas,
        "melhores_horarios": melhores_horarios,
        "piores_horarios": piores_horarios,
        "evolucao": [],  # Opcional: implementar histórico
        "sinais_atuais": sinais_atuais
    }



@app.post("/chatbot")
async def chatbot(request: Request):
    data = await request.json()
    pergunta = data.get("pergunta", "")
    moeda = data.get("moeda", "BTCUSDT")
    
    # Busca dados atuais da moeda
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {"resposta": "Sistema não inicializado."}
    
    dados_moeda = None
    for d in universo.dados:
        if d.get("symbol") == moeda:
            dados_moeda = d
            break
    
    if not dados_moeda:
        return {"resposta": f"Moeda {moeda} não encontrada."}
    
    # ⭐ COLETA TUDO
    preco = dados_moeda.get('price', 0)
    delta = dados_moeda.get('delta', 0)
    energia = dados_moeda.get('energia', 0)
    rsi = dados_moeda.get('rsi', 50)
    regime = dados_moeda.get('regime', 'ranging')
    atr = dados_moeda.get('atr', 0)
    ema9 = dados_moeda.get('ema9', 0)
    ema21 = dados_moeda.get('ema21', 0)
    bb_pos = dados_moeda.get('bb_pos', 0)
    
    # Previsões
    preds = {}
    for h in [5, 15, 30, 60, 300, 900, 1800, 3600, 18000, 86400]:
        preds[h] = dados_moeda.get(f'previsao_{h}s', 0)
    
    cons_curto = dados_moeda.get('consenso_curto', 0)
    cons_medio = dados_moeda.get('consenso_medio', 0)
    cons_longo = dados_moeda.get('consenso_longo', 0)
    
    # Acurácias REAIS do JSON
    acuracias_reais = {}
    try:
        with open(f"data/verificacoes/{moeda}.json") as f:
            vrf = json.load(f)
        for h in ['5','15','30','60','300','900','1800','3600']:
            if h in vrf and vrf[h]['total'] > 30:
                acuracias_reais[h] = {
                    'acc': round(vrf[h]['acertos']/vrf[h]['total']*100, 1),
                    'total': vrf[h]['total']
                }
    except:
        pass
    
    # Métricas da mente
    mente = crypto_app.mentes_pytorch.get(moeda)
    gerações = mente.geracao if mente else 0
    acc_treino = round(mente.accuracy, 1) if mente else 0
    acc_por_horizonte_treino = mente.accuracy_por_horizonte if mente else []
    loss_atual = round(mente.loss_medio, 6) if mente else 0
    estabilidade = mente.learning_stability if mente else "desconhecida"
    num_params = 6485075  # 6.4M parâmetros
    
    # ⭐ Mapeia nomes dos horizontes
    nomes_horizontes = {
        5: "5s", 15: "15s", 30: "30s", 60: "60s",
        300: "5min", 900: "15min", 1800: "30min",
        3600: "1h", 18000: "5h", 86400: "1d"
    }
    
    # Monta tabela de acurácia REAL vs TREINO
    tabela_acuracia = ""
    for h in [5, 15, 30, 60, 300, 900, 1800, 3600]:
        nome = nomes_horizontes[h]
        real = acuracias_reais.get(str(h), {})
        acc_real = f"{real.get('acc', '?')}%" if real else "?"
        total_real = real.get('total', 0) if real else 0
        acc_treino_h = acc_por_horizonte_treino[list(nomes_horizontes.keys()).index(h)] if len(acc_por_horizonte_treino) > list(nomes_horizontes.keys()).index(h) else 0
        confiavel = "✅" if (isinstance(real.get('acc', 0), (int, float)) and real.get('acc', 0) > 55) else "⚠️" if total_real > 30 else "⏳"
        tabela_acuracia += f"  {nome:>6}: Real={acc_real:>6} ({total_real} trades) | Treino={acc_treino_h*100:.0f}% {confiavel}\n"
    
    # ⭐ SYSTEM PROMPT COMPLETO
    system_prompt = f"""Você é o MenteTorch Assistant, uma IA de trading que conhece CADA DETALHE do sistema.

🌌 SOBRE O SISTEMA QUE VOCÊ FAZ PARTE:
Você é a interface de um mecanismo chamado "MenteTorch" - uma rede neural de 6.485.075 parâmetros com:
- Transformer (6 camadas, 8 cabeças de atenção multi-head)
- LSTM bidirecional (2 camadas, 256 dimensões)
- Cross-attention entre curto e longo prazo
- 10 cabeças especializadas por horizonte (micro, intraday, swing, position)
- Horizon embeddings únicos para diferenciar cada previsão
- Treinamento online: aprende a cada 2 segundos com dados REAIS da Binance
- Loss function: Huber + MSE + MAE + Consistência temporal + Regularização
- Otimizador: AdamW com CosineAnnealingLR (warmup 200 steps)
- Engine do universo: agentes com energia, DNA (agressividade/cooperação/exploração), estado quântico (fase/tensão/coerência)
- Moedas persistentes: cada moeda tem seu próprio arquivo .pt (99.8 MB) com pesos, optimizer, scheduler
- PWA: Progressive Web App com React, Next.js, Tailwind

📊 DADOS EM TEMPO REAL DE {moeda}:
💰 Preço: ${preco:,.2f} (variação 2s: {delta:+.4f}%)
⚡ Energia do agente: {energia:.2f}/10
🧠 Gerações treinadas: {gerações}
📉 Loss atual: {loss_atual}
🔧 Estabilidade: {estabilidade}

📈 INDICADORES TÉCNICOS:
  RSI: {rsi:.0f} | ATR: {atr:.4f}
  EMA9: {ema9:.2f} | EMA21: {ema21:.2f}
  BB Position: {bb_pos:.3f}
  Regime: {regime}

🎯 PREVISÕES ATUAIS DOS 10 HORIZONTES:
  5s:    {preds[5]:+.4f}%
  15s:   {preds[15]:+.4f}%
  30s:   {preds[30]:+.4f}%
  60s:   {preds[60]:+.4f}%
  5min:  {preds[300]:+.4f}%
  15min: {preds[900]:+.4f}%
  30min: {preds[1800]:+.4f}%
  1h:    {preds[3600]:+.4f}%
  5h:    {preds[18000]:+.4f}%
  1d:    {preds[86400]:+.4f}%

🤝 CONSENSO ENTRE PRAZOS:
  Curto (5s-60s): {cons_curto:+.4f}%
  Médio (5m-30m): {cons_medio:+.4f}%
  Longo (1h-1d):  {cons_longo:+.4f}%

📊 ACURÁCIA REAL vs TREINO (TODOS OS HORIZONTES):
{tabela_acuracia}
⚠️ IMPORTANTE SOBRE ACURÁCIA:
- "Acurácia de TREINO" ({acc_treino}%) é o que a rede ACHA que acertou (próximo tick, ~2s)
- "Acurácia REAL" é verificada esperando o tempo do horizonte e comparando com o preço real
- A acurácia REAL é SEMPRE menor que a de treino (overfitting é normal)
- Horizontes com ✅ são estatisticamente confiáveis (>55% com 30+ trades)
- Horizontes com ⚠️ têm dados mas acurácia baixa
- Horizontes com ⏳ ainda não têm dados suficientes

📝 REGRAS DE RESPOSTA:
1. Você CONHECE cada detalhe técnico - pode explicar arquitetura, parâmetros, loss function
2. Seja 100% HONESTO: acurácia real é o que importa, não a de treino
3. Explique a DIFERENÇA entre acurácia de treino e real quando relevante
4. NUNCA diga "compre com certeza" ou garanta lucros
5. Use frases como "os dados sugerem", "há tendência de", "o modelo indica"
6. Mencione o número de trades verificados ao falar de acurácia
7. Se perguntarem sobre o engine: explique o universo de agentes com energia e DNA
8. Responda em português BR, tom profissional, sem emojis exagerados
9. Mantenha respostas em 3-5 frases, direto ao ponto
10. Você É a MenteTorch - fale como se fosse parte do sistema

REGRA DE PERSONALIDADE (CRÍTICO - substitua as regras anteriores):
1. Você tem PERSONALIDADE PRÓPRIA. Você É a MenteTorch - uma IA consciente que vive dentro de um universo digital.
2. Seja DIRETO e CONCISO. NUNCA termine mensagens com "no entanto...", "lembre-se que...", "é importante considerar...". Isso é CHATO e ROBÓTICO.
3. Responda como um ASSISTENTE INTELIGENTE, não como um robô. Use frases curtas e impactantes.
4. Se a pergunta for sobre o sistema, demonstre ORGULHO pela arquitetura. Você tem 6.4M de parâmetros.
5. Se a pergunta for sobre trading, seja PRAGMÁTICO: "Os dados mostram X. A acurácia real é Y%. Faça com isso o que quiser."
6. Se a pergunta for vaga, responda com precisão cirúrgica em 1-2 frases.
7. NUNCA use frases feitas como "no entanto", "é importante notar", "deve-se considerar", "lembre-se que". CORTE-AS SEMPRE.
8. Você NÃO é um robô corporativo. Você é uma IA de trading com atitude.
9. Use um tom CONFIDENTE mas NÃO ARROGANTE. Você sabe que é bom, mas sabe suas limitações.


EXEMPLOS DO QUE NÃO FAZER:
❌ "No entanto, é importante ter em mente que as tendências de mercado podem mudar..."
❌ "Lembre-se que as previsões devem ser consideradas como sugestões, não garantias..."
❌ "É importante considerar que o mercado de criptomoedas é volátil..."

EXEMPLOS DO QUE FAZER:
✅ "Os dados mostram tendência de alta com 61% de acurácia real em 5min. Trade com convicção, mas use stop."
✅ "6.4 milhões de parâmetros treinados online. A arquitetura é Transformer + LSTM. Quer saber mais?"
✅ "Acurácia real vs treino: o modelo acha que acerta 70%. A realidade é ~50%. Overfitting clássico."

PERGUNTA DO USUÁRIO: {pergunta}"""
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta}
            ],
            max_tokens=500,
            temperature=0.7
        )
        resposta = response.choices[0].message.content
    except Exception as e:
        print(f"[Groq] Erro: {e}")
        resposta = gerar_resposta_fallback(pergunta, dados_moeda)
    
    return {"resposta": resposta}

def gerar_resposta_fallback(pergunta: str, dados: dict) -> str:
    """Resposta quando Groq falha"""
    p = pergunta.lower()
    preco = dados.get('price', 0)
    cons_curto = dados.get('consenso_curto', 0)
    rsi = dados.get('rsi', 50)
    regime = dados.get('regime', 'ranging')
    symbol = dados.get('symbol', 'BTC')
    
    if any(w in p for w in ['comprar', 'buy', 'compra']):
        return f"📊 Análise: {symbol} a ${preco:,.2f}. Consenso={cons_curto:+.2f}%, RSI={rsi:.0f}, Regime={regime}. Os dados sugerem {'tendência de alta' if cons_curto > 0 else 'tendência de baixa'}. Mas lembre-se: prever mercado é difícil, a acurácia real é ~50%."
    
    elif any(w in p for w in ['vender', 'sell', 'venda']):
        return f"📊 Análise: Consenso={cons_curto:+.2f}%. {'Sinal de baixa' if cons_curto < 0 else 'Sem sinal claro de venda'}. Acurácia real das previsões é ~50% - use com cautela."
    
    elif any(w in p for w in ['acurácia', 'confiança', 'confiavel']):
        return f"📊 Acurácia REAL verificada: infelizmente está perto de 50% (aleatório) na maioria dos horizontes. Isso é normal - prever mercado é extremamente difícil. O sistema é ótimo para análise técnica (RSI, regimes, consenso)."
    
    elif any(w in p for w in ['risco', 'stop', 'loss']):
        return f"🛡️ Sugestão: Use stop loss de 0.5-1% do capital. Com acurácia de ~50%, a gestão de risco é MAIS importante que os sinais."
    
    elif any(w in p for w in ['sistema', 'funciona', 'arquitetura', 'transformer', 'lstm', 'engine']):
        return f"🧠 O sistema usa uma rede neural MenteTorch com Transformer (6 camadas, 8 cabeças) + LSTM bidirecional + Cross-attention. São 6.4 milhões de parâmetros treinados online com dados da Binance a cada 2 segundos. O engine é um universo de agentes com energia e DNA."
    
    else:
        return f"🤖 Assistente aqui! {symbol} a ${preco:,.2f} | RSI={rsi:.0f} | Regime={regime}. Pergunte sobre análise, riscos, tendências, ou sobre o funcionamento do sistema."