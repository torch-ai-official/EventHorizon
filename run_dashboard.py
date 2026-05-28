import threading
import time
import webbrowser
import uvicorn
import subprocess
import socket

from Software.core.universe_instance import universo, lock_universo
from Software.core.leis import evoluir_universo
from Software.core.state import estado
from Software.api import app


terminal_linhas = []
contador = 0
frontend_process = None


# 🔍 verifica se porta está em uso
def porta_em_uso(porta):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) == 0


# 🔥 LOOP DO UNIVERSO
def loop_simulacao():
    print("THREAD SIMULAÇÃO INICIADA")
    global contador

    while True:
        with lock_universo:
            if not estado["pausado"]:
                evoluir_universo(universo, estado, terminal_linhas)

        contador += 1

        if contador % 100 == 0:
            universo.salvar()
            universo.mentes.salvar()

        time.sleep(0.1)


# 🔥 FRONTEND (Next.js na porta 3000)
def start_frontend():
    global frontend_process

    # ⭐ MUDADO: porta do Next.js é 3000
    if porta_em_uso(3000):
        print("Frontend já está rodando na porta 3000")
        return

    print("Iniciando frontend Next.js...")
    frontend_process = subprocess.Popen(
        ["npm.cmd", "run", "dev"],
        cwd="Dashboard"  # ou o nome da sua pasta do frontend
    )


# 🔥 API
def start_api():
    print("Iniciando API...")
    uvicorn.run(app, host="127.0.0.1", port=8000)


# 🔥 AGUARDAR SERVIÇOS
def esperar_servico(porta, nome):
    print(f"Aguardando {nome}...")
    while not porta_em_uso(porta):
        time.sleep(0.5)
    print(f"{nome} pronto!")


# 🔥 INICIALIZAÇÃO
threading.Thread(target=loop_simulacao, daemon=True).start()
threading.Thread(target=start_frontend, daemon=True).start()
threading.Thread(target=start_api, daemon=True).start()

# espera subir
esperar_servico(8000, "API")
esperar_servico(3000, "Frontend Next.js")  # ⭐ MUDADO para 3000

# abre browser
webbrowser.open("http://127.0.0.1:3000")  # ⭐ MUDADO para 3000

# loop principal
while True:
    time.sleep(1)