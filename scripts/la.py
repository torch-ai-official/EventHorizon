# scripts/inspecionar_mentes.py
import torch
import os
from pathlib import Path

def inspecionar_mentes():
    """Mostra TUDO que está salvo dentro dos arquivos .pt"""
    
    pt_path = Path("data/mentes_pytorch")
    arquivos = sorted(pt_path.glob("*.pt"))
    
    if not arquivos:
        print("❌ Nenhum arquivo .pt encontrado em data/mentes_pytorch/")
        return
    
    print("=" * 70)
    print("🧠 INSPEÇÃO COMPLETA DAS MENTES")
    print("=" * 70)
    
    for arquivo in arquivos:
        print(f"\n{'='*70}")
        print(f"📁 Arquivo: {arquivo.name}")
        print(f"   Tamanho: {arquivo.stat().st_size / 1024:.1f} KB")
        print(f"{'='*70}")
        
        try:
            dados = torch.load(arquivo, map_location='cpu')
            
            # Versão
            print(f"   🔢 Versão: {dados.get('versao', 'DESCONHECIDA')}")
            
            # Gerações
            geracao = dados.get('geracao', 0)
            print(f"   🧠 Gerações treinadas: {geracao}")
            
            # Acurácia por horizonte
            n_acertos = dados.get('n_acertos', [0]*10)
            n_erros = dados.get('n_erros', [0]*10)
            
            print(f"\n   📊 ACURÁCIA DE TREINO (próximo tick):")
            horizontes = ['5s','15s','30s','60s','5m','15m','30m','1h','5h','1d']
            for i, h in enumerate(horizontes):
                total = n_acertos[i] + n_erros[i]
                acc = (n_acertos[i] / total * 100) if total > 0 else 0
                bar = "█" * int(acc/10) + "░" * (10-int(acc/10))
                print(f"      {h:>5}: {bar} {acc:5.1f}% ({n_acertos[i]}/{total})")
            
            # Loss history
            historico_loss = dados.get('historico_loss', [])
            if historico_loss:
                loss_inicial = historico_loss[0] if historico_loss else 0
                loss_final = historico_loss[-1] if historico_loss else 0
                print(f"\n   📉 Loss: {loss_inicial:.4f} → {loss_final:.4f} ({len(historico_loss)} registros)")
            
            # Estado interno
            estado = dados.get('estado_interno', None)
            if estado is not None:
                print(f"   🧬 Estado interno: {estado.shape if hasattr(estado, 'shape') else 'presente'}")
            
            # Model state dict
            model_state = dados.get('model_state_dict', {})
            num_params = sum(p.numel() for p in model_state.values()) if model_state else 0
            print(f"   🔧 Parâmetros do modelo: {num_params:,}")
            
            # Optimizer
            opt_state = dados.get('optimizer_state_dict', {})
            print(f"   ⚡ Optimizer: {'✅ salvo' if opt_state else '❌ não salvo'}")
            
            # Scheduler
            sched_state = dados.get('scheduler_state_dict', {})
            print(f"   📈 Scheduler: {'✅ salvo' if sched_state else '❌ não salvo'}")
            
            # Memória de erros
            memoria_erros = dados.get('memoria_erros', [])
            if memoria_erros:
                erro_medio = sum(memoria_erros) / len(memoria_erros)
                print(f"   🎯 Erro médio recente: {erro_medio:.4f}")
            
            # TOTAL de trades
            total_trades = sum(n_acertos) + sum(n_erros)
            print(f"\n   📊 TOTAL de trades registrados: {total_trades:,}")
            
            # Média geral
            if total_trades > 0:
                acc_geral = sum(n_acertos) / total_trades * 100
                print(f"   🎯 Acurácia geral (treino): {acc_geral:.1f}%")
            
        except Exception as e:
            print(f"   ❌ ERRO ao ler: {e}")
    
    print(f"\n{'='*70}")
    print(f"📁 Total de arquivos .pt: {len(arquivos)}")
    print(f"📁 Pasta: {pt_path.absolute()}")
    print(f"{'='*70}")

if __name__ == "__main__":
    inspecionar_mentes()