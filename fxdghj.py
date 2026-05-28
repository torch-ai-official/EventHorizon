# No terminal do backend, encontre o CryptoApp que já está rodando
from Software.core.universe_instance import universo

# Procura o CryptoApp na lista de apps
crypto_app = None
for app in universo.apps:
    if app.nome == "crypto_app":
        crypto_app = app
        break

if crypto_app:
    print("Antes:", crypto_app.ids_cripto)
    removidas = crypto_app.remover_moedas_selecionadas(["BTCUSDT"])
    print("Removidas:", removidas)
    print("Depois:", crypto_app.ids_cripto)
    print("Universo dados:", len(universo.dados))
else:
    print("CryptoApp não encontrado!")