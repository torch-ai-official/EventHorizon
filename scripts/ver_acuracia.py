# scripts/ver_acuracia_insana.py
import torch
import os
from pathlib import Path

def ver_acuracia_insana():
    print("=" * 60)
    print("📊 ACURÁCIA DAS IAS INSANA")
    print("=" * 60)
    
    pt_path = Path("data/mentes_pytorch")
    
    for arquivo in sorted(pt_path.glob("*.pt")):
        dados = torch.load(arquivo, map_location='cpu')
        n_acertos = dados.get('n_acertos', [0,0,0,0])
        n_erros = dados.get('n_erros', [0,0,0,0])
        
        # Identifica qual moeda (baseado no ID)
        id_mente = arquivo.stem.replace("mente_", "")
        
        print(f"\n🧠 Mente {id_mente} ({arquivo.name})")
        print("-" * 40)
        
        for i, (a, e) in enumerate(zip(n_acertos, n_erros)):
            total = a + e
            acc = (a / total * 100) if total > 0 else 0
            horizonte = [5, 15, 30, 60][i]
            
            if acc >= 80:
                status = "🔥 INSANA"
            elif acc >= 60:
                status = "🚀 BOA"
            elif acc >= 45:
                status = "📈 APRENDENDO"
            else:
                status = "⚠️ INICIANDO"
            
            print(f"   {horizonte}s: {acc:.1f}% ({status}) - {a:.1f}/{total:.1f}")

if __name__ == "__main__":
    ver_acuracia_insana()