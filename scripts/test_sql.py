# scripts/ver_tamanho_arquivos.py
import os
from pathlib import Path

pt_path = Path("data/mentes_pytorch")
print("📁 Arquivos .pt encontrados:")
for f in pt_path.glob("*.pt"):
    size = f.stat().st_size
    print(f"   {f.name} - {size} bytes")
    
    # Tenta ler o arquivo
    import torch
    try:
        dados = torch.load(f, map_location='cpu')
        acertos = dados.get('n_acertos', [0,0,0,0])
        print(f"      Acertos: {acertos}")
    except:
        print(f"      ERRO ao ler")