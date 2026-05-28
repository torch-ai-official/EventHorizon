import os
import time
import json

import sqlite3
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
    for d in universo.dados:
        item = {
            "id": f"U{d['id']}",
            "energia": d["energia"],
            "estado": "ativo",
            "symbol": d.get("symbol"),
            "price": d.get("price"),
            "candles": d.get("candles", []),
            "delta": d.get("delta"),
            "tipo": d.get("tipo"),
            "previsao": d.get("previsao", 0),
            "previsao_5s": d.get("previsao_5s", 0),
            "previsao_15s": d.get("previsao_15s", 0),
            "previsao_30s": d.get("previsao_30s", 0),
            "previsao_60s": d.get("previsao_60s", 0),
        }
        # ⭐ LOG PARA VER O QUE ESTÁ SENDO ENVIADO
        if item.get("symbol"):
            print(f"📤 API enviando {item['symbol']}:")
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
    """Retorna estatísticas para o dashboard do trader"""
    from Software.core.mind_sql import get_banco_sql
    banco = get_banco_sql()
    
    # Busca dados do SQL
    performance_moedas = banco.get_performance_por_moeda(10)
    melhores_horarios = banco.get_melhores_horarios(5)
    piores_horarios = banco.get_piores_horarios(3)
    evolucao = banco.get_evolucao_acuracia(7)
    estatisticas = banco.get_estatisticas_gerais()
    
    # Calcula acurácia geral
    total_previsoes = estatisticas.get('total_previsoes', 0)
    total_acertos = estatisticas.get('total_acertos', 0)
    acuracia_geral = round((total_acertos / total_previsoes * 100), 1) if total_previsoes > 0 else 0
    
    # Busca sinais atuais do CryptoApp (em tempo real)
    crypto_app = next((app for app in universo.apps if app.nome == "crypto_app"), None)
    sinais_atuais = []
    if crypto_app:
        for moeda, mente in crypto_app.mentes_pytorch.items():
            # Tenta pegar a previsão atual
            try:
                # features placeholder, o forward real usa dados reais
                previsao_raw = mente.forward([0]*14)[0] if hasattr(mente, 'forward') else 0
                previsao = previsao_raw * 5  # escala para percentual
            except:
                previsao = 0
            
            sinais_atuais.append({
                "symbol": moeda,
                "previsao": round(previsao, 2),
                "confianca": round(mente.accuracy_por_horizonte[0] * 100, 1) if hasattr(mente, 'accuracy_por_horizonte') else 0,
                "acertos": mente.n_acertos[0] if len(mente.n_acertos) > 0 else 0,
                "erros": mente.n_erros[0] if len(mente.n_erros) > 0 else 0,
            })
    
    return {
        "acuracia_geral": acuracia_geral,
        "total_previsoes": total_previsoes,
        "total_acertos": total_acertos,
        "performance_moedas": performance_moedas,
        "melhores_horarios": melhores_horarios,
        "piores_horarios": piores_horarios,
        "evolucao": evolucao,
        "sinais_atuais": sinais_atuais
    }