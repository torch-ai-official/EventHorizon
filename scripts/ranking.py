# resetar_verificacoes.py
"""
Reseta TODOS os arquivos de verificação para começar do zero.
💀☠️ Sapere aude - Dados limpos, sinais honestos.
"""

import json
import os
import shutil
from datetime import datetime

HORIZONTES = [5, 15, 30, 60, 300, 900, 1800, 3600, 18000, 86400]

def resetar():
    pasta = "data/verificacoes"
    backup = f"data/verificacoes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
   
    
    # Lista arquivos
    arquivos = [f for f in os.listdir(pasta) if f.endswith('.json')]
    
    if not arquivos:
        print("❌ Nenhum arquivo encontrado!")
        return
    
    for arquivo in arquivos:
        caminho = os.path.join(pasta, arquivo)
        moeda = arquivo.replace('.json', '')
        
        # Estrutura zerada
        novo = {}
        for h in HORIZONTES:
            novo[str(h)] = {
                "acertos": 0,
                "erros": 0,
                "total": 0,
                "historico": []
            }
        
        with open(caminho, 'w') as f:
            json.dump(novo, f, indent=2)
        
        print(f"✅ {moeda}: zerado")
    
    print(f"\n💀 {len(arquivos)} moedas resetadas.")
    print("💀 O sistema vai começar a acumular dados LIMPOS.")
    print("💀 Aguarde 24-48h antes de confiar nas acurácias.")

if __name__ == "__main__":
    print("\n" + "💀" * 30)
    print("⚠️  RESET DE VERIFICAÇÕES")
    print("💀" * 30)
    resposta = input("\nTem certeza? Os dados antigos serão perdidos! (s/n): ")
    
    if resposta.lower() == 's':
        resetar()
    else:
        print("Cancelado.")