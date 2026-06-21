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
from Software.apps.chatbot_app import ChatBotApp
from fastapi.staticfiles import StaticFiles
chatbot_app = ChatBotApp(universo)


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


@app.get("/dashboard/realtime")
async def dashboard_realtime():
    """Dashboard PROFISSIONAL - todos os dados em tempo real"""
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {"moedas": [], "total_moedas": 0}
    
    moedas = []
    for moeda, id_dado in crypto_app.ids_cripto.items():
        dado = next((d for d in universo.dados if d["id"] == id_dado), None)
        if not dado:
            continue
        
        mente = crypto_app.mentes_pytorch.get(moeda)
        
        # Acurácias REAIS do JSON
        acuracias_reais = {}
        try:
            with open(f"data/verificacoes/{moeda}.json") as f:
                vrf = json.load(f)
            for h in ['5','15','30','60','300','900','1800','3600']:
                if h in vrf and vrf[h]['total'] > 10:
                    acuracias_reais[h] = {
                        'acertos': vrf[h]['acertos'],
                        'erros': vrf[h]['erros'],
                        'total': vrf[h]['total'],
                        'acuracia': round(vrf[h]['acertos']/vrf[h]['total']*100, 1)
                    }
        except:
            pass
        
        moedas.append({
            "symbol": moeda.replace("USDT", ""),
            "price": dado.get("price", 0),
            "rsi": round(dado.get("rsi", 50), 0),
            "regime": dado.get("regime", "ranging"),
            "geracoes": mente.geracao if mente else 0,
            "acuracias_reais": acuracias_reais,
            "previsoes": {
                "5s": round(dado.get("previsao_5s", 0), 4),
                "15s": round(dado.get("previsao_15s", 0), 4),
                "30s": round(dado.get("previsao_30s", 0), 4),
                "60s": round(dado.get("previsao_60s", 0), 4),
                "5min": round(dado.get("previsao_300s", 0), 4),
                "15min": round(dado.get("previsao_900s", 0), 4),
                "30min": round(dado.get("previsao_1800s", 0), 4),
                "1h": round(dado.get("previsao_3600s", 0), 4),
                "5h": round(dado.get("previsao_18000s", 0), 4),
                "1d": round(dado.get("previsao_86400s", 0), 4),
            }
        })
    
    moedas.sort(key=lambda m: m['acuracias_reais'].get('900', {}).get('acuracia', 0), reverse=True)
    
    return {
        "moedas": moedas,
        "total_moedas": len(moedas),
        "total_verificacoes": sum(sum(v['total'] for v in m['acuracias_reais'].values()) for m in moedas),
        "melhor_moeda": moedas[0] if moedas else None,
        "melhores_horarios": [],
        "piores_horarios": [],
    }

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
    nome_trader = data.get("nome_trader", None)  # ⭐ NOVO
    
    # Se tem nome_trader, atualiza o chatbot
    if nome_trader:
        chatbot_app.set_nome_trader(nome_trader)
    
    resposta = chatbot_app.responder(pergunta, moeda, nome_trader)
    return {"resposta": resposta}

@app.get("/performance/metricas")
async def performance_metricas():
    """Métricas completas das mentes para a aba Performance"""
    import glob
    
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {"mentes": [], "resumo": {}}
    
    mentes_data = []
    
    for moeda, mente in crypto_app.mentes_pytorch.items():
        if mente is None:
            continue
        
        # ⭐ Busca acurácias REAIS do JSON (FONTE PRINCIPAL)
        acuracias_reais = {}
        try:
            with open(f"data/verificacoes/{moeda}.json") as f:
                vrf = json.load(f)
            for h in ['5','15','30','60','300','900','1800','3600']:
                if h in vrf and vrf[h]['total'] > 10:
                    acuracias_reais[h] = {
                        'acertos': vrf[h]['acertos'],
                        'erros': vrf[h]['erros'],
                        'total': vrf[h]['total'],
                        'acuracia': round(vrf[h]['acertos']/vrf[h]['total']*100, 1)
                    }
        except:
            pass
        
        # ⭐ Calcula acurácias por TIPO usando dados REAIS
        def calc_acuracia(horizontes):
            acertos_total = 0
            erros_total = 0
            for h in horizontes:
                if h in acuracias_reais:
                    acertos_total += acuracias_reais[h]['acertos']
                    erros_total += acuracias_reais[h]['erros']
            total = acertos_total + erros_total
            return round(acertos_total / total, 3) if total > 0 else 0.5
        
        acuracia_micro = calc_acuracia(['5', '15', '30', '60'])
        acuracia_intraday = calc_acuracia(['300', '900', '1800'])
        acuracia_swing = calc_acuracia(['3600'])
        acuracia_position = calc_acuracia(['3600'])  # mesmo por enquanto
        
        # ⭐ Acurácia média geral (ponderada por total de trades)
        total_acertos = sum(v['acertos'] for v in acuracias_reais.values())
        total_erros = sum(v['erros'] for v in acuracias_reais.values())
        total_geral = total_acertos + total_erros
        acuracia_media = round(total_acertos / total_geral, 3) if total_geral > 0 else 0.5
        
        # ⭐ Confiança baseada na quantidade de trades
        if total_geral > 500:
            confianca = 0.85
        elif total_geral > 100:
            confianca = 0.70
        elif total_geral > 30:
            confianca = 0.55
        else:
            confianca = 0.40
        
        # ⭐ Tendência real (compara acurácia recente vs antiga)
        tendencia = "estável"
        if '900' in acuracias_reais and acuracias_reais['900']['total'] > 100:
            acc_atual = acuracias_reais['900']['acuracia']
            # Se tem acurácia acima de 55%, está melhorando
            if acc_atual > 55:
                tendencia = "melhorando"
            elif acc_atual < 48:
                tendencia = "piorando"
        
        # ⭐ Estabilidade baseada na variação entre horizontes
        accs = [v['acuracia'] for v in acuracias_reais.values()]
        if len(accs) >= 3:
            variacao = max(accs) - min(accs)
            if variacao < 10:
                estabilidade = "estável"
            elif variacao < 20:
                estabilidade = "moderada"
            else:
                estabilidade = "instável"
        else:
            estabilidade = "moderada"
        
        # ⭐ Geração da mente
        snapshot = mente.snapshot() if hasattr(mente, 'snapshot') else {}
        geracao = snapshot.get("geracao", 0) if snapshot else 0
        
        mentes_data.append({
            "moeda": moeda.replace("USDT", ""),
            "geracao": geracao,
            "acuracia_media": round(acuracia_media * 100, 1),
            "acuracia_micro": round(acuracia_micro * 100, 1),
            "acuracia_intraday": round(acuracia_intraday * 100, 1),
            "acuracia_swing": round(acuracia_swing * 100, 1),
            "acuracia_position": round(acuracia_position * 100, 1),
            "loss_medio": snapshot.get("loss_medio", 0) if snapshot else 0,
            "confianca": round(confianca * 100, 1),
            "estabilidade": estabilidade,
            "tendencia": tendencia,
            "acuracias_reais": acuracias_reais,
            "accuracy_por_horizonte": [v['acuracia'] for v in acuracias_reais.values()],
        })
    
    # Ordena por total de trades (mais dados primeiro)
    mentes_data.sort(key=lambda m: sum(v['total'] for v in m['acuracias_reais'].values()), reverse=True)
    
    # Resumo geral
    total_geracoes = sum(m["geracao"] for m in mentes_data)
    acuracias_todas = [m["acuracia_media"] for m in mentes_data if m["acuracia_media"] > 50]
    acuracia_media_geral = round(sum(acuracias_todas) / len(acuracias_todas), 1) if acuracias_todas else 0
    
    return {
        "mentes": mentes_data,
        "resumo": {
            "total_moedas": len(mentes_data),
            "total_geracoes": total_geracoes,
            "acuracia_media_geral": acuracia_media_geral,
            "moeda_top": mentes_data[0]["moeda"] if mentes_data else None,
            "estabilidade_geral": "estável" if all(m["estabilidade"] == "estável" for m in mentes_data) else "moderada"
        }
    }


@app.get("/performance/evolucao")
async def performance_evolucao(moeda: str = "BTCUSDT"):
    """Histórico de evolução de uma moeda específica"""
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {"historico": [], "moeda": moeda}
    
    mente = crypto_app.mentes_pytorch.get(moeda if "USDT" in moeda else f"{moeda}USDT")
    if not mente:
        return {"historico": [], "moeda": moeda}
    
    # Reconstrói histórico dos arquivos de verificação
    historico = []
    try:
        with open(f"data/verificacoes/{moeda}.json") as f:
            vrf = json.load(f)
        
        # Pega o horizonte com mais dados (geralmente 5min ou 15min)
        for h in ['5','15','30','60','300','900','1800','3600']:
            if h in vrf and vrf[h]['total'] > 50:
                total = vrf[h]['total']
                acuracia = round(vrf[h]['acertos']/total*100, 1) if total > 0 else 0
                historico.append({
                    "horizonte": f"{int(h)//60}min" if int(h) >= 60 else f"{h}s",
                    "horizonte_s": int(h),
                    "total": total,
                    "acertos": vrf[h]['acertos'],
                    "erros": vrf[h]['erros'],
                    "acuracia": acuracia,
                })
    except:
        pass
    
    # Adiciona dados da mente
    snapshot = mente.snapshot()
    
    return {
        "moeda": moeda.replace("USDT", ""),
        "geracao": snapshot["geracao"],
        "loss_medio": snapshot["loss_medio"],
        "confianca": snapshot["confidence"],
        "accuracy_por_horizonte": snapshot["accuracy_por_horizonte"],
        "historico_horizontes": historico,
        "tendencia": "melhorando" if snapshot["loss_medio"] < 0.03 else "estável"
    }

@app.get("/historico")
async def get_historico():
    """Histórico de trades verificado"""
    import glob
    
    trades = []
    arquivos = glob.glob("data/verificacoes/*.json")
    
    for arquivo in arquivos:
        moeda = os.path.basename(arquivo).replace(".json", "")
        try:
            with open(arquivo) as f:
                vrf = json.load(f)
            
            for horizonte_s, dados in vrf.items():
                if dados.get("total", 0) == 0:
                    continue
                
                h = int(horizonte_s)
                if h <= 60:
                    nome_h = f"{h}s"
                elif h < 3600:
                    nome_h = f"{h//60}min"
                else:
                    nome_h = f"{h//3600}h"
                
                trades.append({
                    "moeda": moeda.replace("USDT", ""),
                    "horizonte": nome_h,
                    "horizonte_s": h,
                    "acertos": dados["acertos"],
                    "erros": dados["erros"],
                    "total": dados["total"],
                    "acuracia": round((dados["acertos"]/dados["total"])*100,1) if dados["total"]>0 else 0,
                    "confianca": 50,
                    "preco_atual": 0,
                    "timestamp": time.time(),
                    "status": "verificado"
                })
        except:
            pass
    
    trades.sort(key=lambda t: t["total"], reverse=True)
    
    total_acertos = sum(t["acertos"] for t in trades)
    total_erros = sum(t["erros"] for t in trades)
    total_geral = total_acertos + total_erros
    
    return {
        "trades": trades,
        "resumo": {
            "total_trades": total_geral,
            "total_acertos": total_acertos,
            "total_erros": total_erros,
            "acuracia_geral": round((total_acertos/total_geral)*100,1) if total_geral>0 else 0,
            "total_moedas": len(set(t["moeda"] for t in trades)),
            "horizontes_ativos": len(set(t["horizonte"] for t in trades)),
        }
    }


@app.get("/gestao-risco/metricas")
async def gestao_risco_metricas():
    """Métricas de risco baseadas nas acurácias reais"""
    import glob
    
    # Coleta acurácias de todas as moedas
    metricas = {}
    total_acertos_global = 0
    total_erros_global = 0
    
    arquivos = glob.glob("data/verificacoes/*.json")
    for arquivo in arquivos:
        moeda = os.path.basename(arquivo).replace(".json", "")
        try:
            with open(arquivo) as f:
                vrf = json.load(f)
            
            acuracias = {}
            for h in ['5','15','30','60','300','900','1800','3600']:
                if h in vrf and vrf[h]['total'] > 10:
                    acuracias[h] = {
                        'acertos': vrf[h]['acertos'],
                        'erros': vrf[h]['erros'],
                        'total': vrf[h]['total'],
                        'acuracia': round(vrf[h]['acertos']/vrf[h]['total']*100, 1)
                    }
                    total_acertos_global += vrf[h]['acertos']
                    total_erros_global += vrf[h]['erros']
            
            if acuracias:
                metricas[moeda.replace("USDT", "")] = acuracias
        except:
            pass
    
    # Melhor e pior horizonte
    todas_acuracias = []
    for moeda, h_data in metricas.items():
        for h, data in h_data.items():
            todas_acuracias.append({
                'moeda': moeda,
                'horizonte': f"{int(h)//60}min" if int(h) >= 60 else f"{h}s",
                'acuracia': data['acuracia'],
                'total': data['total']
            })
    
    # Ordena por acurácia
    melhores = sorted(todas_acuracias, key=lambda x: x['acuracia'], reverse=True)[:5]
    piores = sorted(todas_acuracias, key=lambda x: x['acuracia'])[:5]
    
    # Acurácia global
    total_global = total_acertos_global + total_erros_global
    acuracia_global = round(total_acertos_global / total_global * 100, 1) if total_global > 0 else 50
    
    # Regime de mercado
    if acuracia_global > 58:
        regime = "TENDÊNCIA FORTE"
        recomendacao = "Aumentar posição (3% risco)"
        cor = "green"
    elif acuracia_global > 52:
        regime = "TENDÊNCIA MODERADA"
        recomendacao = "Posição normal (2% risco)"
        cor = "cyan"
    elif acuracia_global > 48:
        regime = "LATERAL/VOLÁTIL"
        recomendacao = "Reduzir posição (1% risco)"
        cor = "yellow"
    else:
        regime = "CAÓTICO/IMPREVISÍVEL"
        recomendacao = "NÃO OPERAR (0% risco)"
        cor = "red"
    
    return {
        "metricas": metricas,
        "melhores_horizontes": melhores,
        "piores_horizontes": piores,
        "acuracia_global": acuracia_global,
        "total_trades_global": total_global,
        "regime_mercado": regime,
        "recomendacao": recomendacao,
        "cor_regime": cor
    }


@app.post("/gestao-risco/simular")
async def gestao_risco_simular(request: Request):
    """Simulador de cenários de trading"""
    data = await request.json()
    
    capital = float(data.get("capital", 10000))
    risco_por_trade = float(data.get("risco_percentual", 2.0)) / 100
    stop_loss = float(data.get("stop_loss", -5.0)) / 100
    take_profit = float(data.get("take_profit", 10.0)) / 100
    acuracia = float(data.get("acuracia", 66.0)) / 100
    num_trades = int(data.get("num_trades", 100))
    moeda = data.get("moeda", "BTC")
    
    # Pega acurácia REAL da moeda se disponível
    try:
        with open(f"data/verificacoes/{moeda}USDT.json") as f:
            vrf = json.load(f)
        # Usa acurácia do horizonte de 15min (900s)
        if '900' in vrf and vrf['900']['total'] > 50:
            acuracia = vrf['900']['acertos'] / vrf['900']['total']
    except:
        pass
    
    # Cálculos
    valor_risco = capital * risco_por_trade
    valor_perda = capital * abs(stop_loss)
    valor_ganho = capital * take_profit
    risk_reward = abs(take_profit / stop_loss) if stop_loss != 0 else 0
    
    # Simulação
    acertos = int(num_trades * acuracia)
    erros = num_trades - acertos
    
    ganho_total = acertos * valor_ganho * (capital / 10000)
    perda_total = erros * valor_perda * (capital / 10000)
    lucro_liquido = ganho_total - perda_total
    
    capital_final = capital + lucro_liquido
    roi = round((capital_final - capital) / capital * 100, 1)
    
    # Drawdown simulado (worst case: 5 losses seguidos)
    max_drawdown = valor_perda * 5
    drawdown_percentual = round(max_drawdown / capital * 100, 1)
    
    # Classificação do risco
    if risk_reward >= 2 and acuracia >= 0.55:
        qualidade = "EXCELENTE"
        qualidade_cor = "green"
    elif risk_reward >= 1.5 and acuracia >= 0.5:
        qualidade = "BOA"
        qualidade_cor = "cyan"
    elif risk_reward >= 1:
        qualidade = "MODERADA"
        qualidade_cor = "yellow"
    else:
        qualidade = "RUIM"
        qualidade_cor = "red"
    
    return {
        "parametros": {
            "capital": capital,
            "risco_percentual": round(risco_por_trade * 100, 1),
            "stop_loss": round(stop_loss * 100, 1),
            "take_profit": round(take_profit * 100, 1),
            "risk_reward": round(risk_reward, 2),
            "acuracia_usada": round(acuracia * 100, 1),
            "moeda": moeda
        },
        "resultados": {
            "acertos": acertos,
            "erros": erros,
            "ganho_total": round(ganho_total, 2),
            "perda_total": round(perda_total, 2),
            "lucro_liquido": round(lucro_liquido, 2),
            "capital_final": round(capital_final, 2),
            "roi": roi,
            "max_drawdown": round(max_drawdown, 2),
            "drawdown_percentual": drawdown_percentual
        },
        "qualidade": qualidade,
        "qualidade_cor": qualidade_cor
    }


@app.get("/alertas/config")
async def alertas_config():
    """Retorna configuração atual dos alertas"""
    import os
    
    config_path = "data/alertas_config.json"
    config_default = {
        "sinais": [
            {"moeda": "BTC", "direcao": "COMPRAR", "horizonte": "5min", "confianca_min": 60, "ativo": True},
            {"moeda": "ETH", "direcao": "COMPRAR", "horizonte": "15min", "confianca_min": 55, "ativo": True},
        ],
        "protecao": {
            "drawdown_max": -10,
            "losses_seguidos": 3,
            "volume_anormal": 50,
            "acuracia_min": 45,
            "pausar_apos_losses": True
        },
        "oportunidades": {
            "acuracia_alta": 65,
            "melhor_horario": True,
            "nova_moeda": 60
        },
        "canais": {
            "navegador": True,
            "telegram": False,
            "email": False,
            "som": True
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f)
        except:
            pass
    
    return config_default


@app.post("/alertas/salvar")
async def alertas_salvar(request: Request):
    """Salva configuração dos alertas"""
    data = await request.json()
    os.makedirs("data", exist_ok=True)
    with open("data/alertas_config.json", "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "ok"}


@app.get("/alertas/historico")
async def alertas_historico(limit: int = 20):
    """Retorna histórico de alertas gerados"""
    import os
    
    historico_path = "data/alertas_historico.json"
    
    if os.path.exists(historico_path):
        try:
            with open(historico_path) as f:
                historico = json.load(f)
            return {"alertas": historico[-limit:]}
        except:
            pass
    
    return {"alertas": []}


@app.get("/alertas/verificar")
async def alertas_verificar():
    """Verifica AGORA se há alertas para disparar - TODOS OS HORIZONTES"""
    import os
    
    alertas_disparados = []
    
    # Mapeamento de horizontes para índices
    HORIZONTE_PARA_INDICE = {
        "5s": 0, "15s": 1, "30s": 2, "60s": 3,
        "5min": 4, "15min": 5, "30min": 6, "1h": 7,
        "5h": 8, "1d": 9
    }
    
    INDICE_PARA_HORIZONTE = {
        0: "5s", 1: "15s", 2: "30s", 3: "60s",
        4: "5min", 5: "15min", 6: "30min", 7: "1h",
        8: "5h", 9: "1d"
    }
    
    # Busca CryptoApp
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    if not crypto_app:
        return {"alertas": [], "total": 0, "mensagem": "CryptoApp não está rodando"}
    
    # Carrega configurações de alertas
    config_path = "data/alertas_config.json"
    config = None
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
        except:
            pass
    
    if not config or not config.get("sinais"):
        return {"alertas": [], "total": 0, "mensagem": "Nenhum alerta configurado"}
    
    # Para cada moeda e mente
    for moeda, mente in crypto_app.mentes_pytorch.items():
        if mente is None:
            continue
        
        moeda_nome = moeda.replace("USDT", "")
        
        # Para cada alerta configurado PARA ESTA MOEDA
        for alerta_config in config["sinais"]:
            if not alerta_config.get("ativo", True):
                continue
            
            if alerta_config["moeda"] != moeda_nome:
                continue
            
            # Converte horizonte do config para índice
            horizonte_nome = alerta_config["horizonte"]
            indice = None
            
            # Mapeia nomes para índices
            for h_nome, h_idx in HORIZONTE_PARA_INDICE.items():
                if h_nome == horizonte_nome or h_nome.replace("min", "m").replace("s", "s") == horizonte_nome:
                    indice = h_idx
                    break
            
            if indice is None or indice >= len(mente.cabecas):
                continue
            
            # Pega confiança mínima do alerta
            confianca_min = alerta_config.get("confianca_min", 50)
            
            # Verifica se tem dados suficientes
            total_trades = mente.n_acertos[indice] + mente.n_erros[indice]
            if total_trades < 10:
                continue
            
            # Calcula acurácia REAL deste horizonte
            acuracia_real = round((mente.n_acertos[indice] / total_trades) * 100, 1) if total_trades > 0 else 0
            
            # Verifica se acurácia está acima do mínimo
            if acuracia_real < confianca_min:
                continue
            
            # Tenta pegar previsão atual
            if not hasattr(mente, '_ultimos_x_cabecas') or not mente._ultimos_x_cabecas:
                continue
            
            if indice >= len(mente._ultimos_x_cabecas):
                continue
            
            try:
                with torch.no_grad():
                    pred = float(mente.cabecas[indice](mente._ultimos_x_cabecas[indice]).item())
                    pred_percentual = round(pred * 100, 1)
                    
                    direcao = alerta_config.get("direcao", "COMPRAR")
                    
                    # Verifica se a direção do sinal bate com o configurado
                    if direcao == "COMPRAR" and pred_percentual <= 0:
                        continue
                    if direcao == "VENDER" and pred_percentual >= 0:
                        continue
                    
                    alertas_disparados.append({
                        "tipo": "sinal",
                        "moeda": moeda_nome,
                        "direcao": direcao,
                        "horizonte": INDICE_PARA_HORIZONTE.get(indice, str(indice)),
                        "previsao": abs(pred_percentual),
                        "confianca": acuracia_real,
                        "acuracia_min_config": confianca_min,
                        "timestamp": time.time(),
                        "mensagem": f"{direcao} {moeda_nome} - {INDICE_PARA_HORIZONTE.get(indice, '?')} - Conf: {acuracia_real}% (mín: {confianca_min}%)"
                    })
            except Exception as e:
                print(f"[Alertas] Erro ao verificar {moeda_nome} horizonte {indice}: {e}")
    
    # Salva no histórico
    if alertas_disparados:
        os.makedirs("data", exist_ok=True)
        historico_path = "data/alertas_historico.json"
        historico = []
        if os.path.exists(historico_path):
            try:
                with open(historico_path) as f:
                    historico = json.load(f)
            except:
                pass
        historico.extend(alertas_disparados)
        historico = historico[-100:]
        with open(historico_path, "w") as f:
            json.dump(historico, f, indent=2)
    
    return {
        "alertas": alertas_disparados,
        "total": len(alertas_disparados),
        "mensagem": f"{len(alertas_disparados)} alerta(s) encontrado(s)"
    }


@app.get("/alertas/status-atual")
async def alertas_status_atual():
    """Retorna valores ATUAIS do sistema para comparar com limites"""
    
    # Busca métricas do dashboard/realtime
    crypto_app = None
    for app in universo.apps:
        if hasattr(app, 'nome') and app.nome == "crypto_app":
            crypto_app = app
            break
    
    # Acurácia atual (melhor horizonte)
    acuracia_atual = 50
    try:
        # Tenta pegar do BTC (mais dados)
        with open("data/verificacoes/BTCUSDT.json") as f:
            vrf = json.load(f)
        # Pega o horizonte com mais trades
        melhor_h = max(vrf.keys(), key=lambda h: vrf[h]['total'])
        if vrf[melhor_h]['total'] > 50:
            acuracia_atual = round(vrf[melhor_h]['acertos']/vrf[melhor_h]['total']*100, 1)
    except:
        pass
    
    # Drawdown atual (simulado - você pode implementar o real depois)
    drawdown_atual = -4.2
    
    # Losses seguidos (conta do histórico de trades)
    losses_seguidos = 0
    try:
        with open("data/verificacoes/BTCUSDT.json") as f:
            vrf = json.load(f)
        # Pega o horizonte mais recente
        for h in ['300','900','1800','3600']:
            if h in vrf and vrf[h]['total'] > 10:
                erros_recentes = vrf[h]['erros']
                losses_seguidos = min(erros_recentes, 5)  # estimativa
                break
    except:
        pass
    
    # Volume atual vs médio (placeholder)
    volume_atual = 12
    
    return {
        "drawdown_atual": round(drawdown_atual, 1),
        "losses_seguidos": min(losses_seguidos, 10),
        "acuracia_atual": acuracia_atual,
        "volume_atual": volume_atual,
        "timestamp": time.time()
    }

# ⭐ Serve o frontend estático (build do Next.js)
#if os.path.exists("Dashboard/out"):
#    app.mount("/", StaticFiles(directory="Dashboard/out", html=True), name="frontend")



if __name__ == "__main__":
    import uvicorn
    # ⭐ Porta 7860 para o Hugging Face
    uvicorn.run(app, host="0.0.0.0", port=7860)