from Software.core.universe_instance import universo
from Software.apps.crypto_app import CryptoApp

crypto = CryptoApp(universo)
crypto.spawn_moedas(["BTCUSDT", "ETHUSDT"])

# Simula o stop (sem remover)
crypto.ativo = False
crypto.rodando_api = False

# Gera relatório
print(crypto.gerar_relatorio_desempenho())