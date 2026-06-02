# scripts/limpar_corrompidos.py
import os
import torch
from pathlib import Path

corruptos = 0
for pt in Path("data/mentes_pytorch").glob("*.pt"):
    try:
        _ = torch.load(pt, map_location='cpu')
    except:
        print(f"Removendo {pt.name} (corrompido)")
        os.remove(pt)
        corruptos += 1
print(f"Removidos {corruptos} arquivos corrompidos")