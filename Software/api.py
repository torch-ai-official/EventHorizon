import os
import time

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
    for d in universo.dados:
        print(f"id={d['id']} tipo={d.get('tipo')} symbol={d.get('symbol')} price={d.get('price')}")
        
    return {
        "energia_total": universo.status_universo()["energia_total"],

        "dados": [
            {
                "id": f"U{d['id']}",
                "energia": d["energia"],
                "estado": "ativo",

                "symbol": d.get("symbol"),
                "price": d.get("price"),
                "candles": d.get("candles", []),
                "delta": d.get("delta"),
                "tipo": d.get("tipo"),
                "previsao": d.get("previsao", 0)
            }
            for d in universo.dados
        ],

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

