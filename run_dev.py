import threading
import webbrowser
import time
import uvicorn

def start_api():
    uvicorn.run("Software.api:app", host="127.0.0.1", port=8000, reload=False)

# inicia API na mesma aplicação (thread)
threading.Thread(target=start_api, daemon=True).start()

# espera a API subir
time.sleep(2)

# abre dashboard
webbrowser.open("http://127.0.0.1:8000")

# AGORA importa e roda o software
from Software.core.software import main

main()