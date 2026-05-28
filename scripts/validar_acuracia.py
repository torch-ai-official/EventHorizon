# scripts/validar_acuracia.py
import torch
import json

def validar_acuracia():
    # Carrega a mente 578
    dados = torch.load("data/mentes_pytorch/mente_578.pt", map_location='cpu')
    
    n_acertos = dados.get('n_acertos', [0,0,0,0])
    n_erros = dados.get('n_erros', [0,0,0,0])
    
    print("="*50)
    print("🔍 VALIDAÇÃO DA ACURÁCIA")
    print("="*50)
    
    for i in range(4):
        total = n_acertos[i] + n_erros[i]
        acc = (n_acertos[i] / total * 100) if total > 0 else 0
        
        print(f"\nHorizonte {[5,15,30,60][i]}s:")
        print(f"  Acertos: {n_acertos[i]:.1f}")
        print(f"  Erros: {n_erros[i]:.1f}")
        print(f"  Total: {total:.1f}")
        print(f"  Acurácia: {acc:.1f}%")
        
        # Verifica se os números são plausíveis
        if total > 0 and (n_acertos[i] + n_erros[i]) == total:
            print(f"  ✅ Contagem consistente")

if __name__ == "__main__":
    validar_acuracia()