# scripts/inspecionar_mentes_completo.py
import torch
import os
import json
from pathlib import Path
from datetime import datetime

def inspecionar_mentes():
    """Mostra TUDO que está salvo dentro dos arquivos .pt + verificações"""
    
    pt_path = Path("data/mentes_pytorch")
    vrf_path = Path("data/verificacoes")
    
    arquivos = sorted(pt_path.glob("*.pt"))
    
    if not arquivos:
        print("❌ Nenhum arquivo .pt encontrado!")
        return
    
    print("=" * 70)
    print(f"🧠 RELATÓRIO COMPLETO - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 70)
    
    for arquivo in arquivos:
        nome = arquivo.stem.replace("mente_", "")
        tamanho_mb = arquivo.stat().st_size / (1024 * 1024)
        
        print(f"\n{'='*70}")
        print(f"📁 {nome}")
        print(f"   Tamanho: {tamanho_mb:.1f} MB")
        print(f"{'='*70}")
        
        try:
            dados = torch.load(arquivo, map_location='cpu')
            
            # Info básica
            versao = dados.get('versao', '?')
            geracao = dados.get('geracao', 0)
            print(f"   🔢 Versão: {versao}")
            print(f"   🧠 Gerações: {geracao:,}")
            
            # Acurácia de TREINO por horizonte
            n_acertos = dados.get('n_acertos', [0]*10)
            n_erros = dados.get('n_erros', [0]*10)
            horizontes = ['5s','15s','30s','60s','5m','15m','30m','1h','5h','1d']
            
            print(f"\n   📊 ACURÁCIA DE TREINO:")
            print(f"   {'Horiz.':<6} {'Acertos':<10} {'Erros':<10} {'Total':<10} {'Acc %':<8} {'Barra'}")
            print(f"   {'-'*55}")
            
            total_geral = 0
            for i, h in enumerate(horizontes):
                a = n_acertos[i] if i < len(n_acertos) else 0
                e = n_erros[i] if i < len(n_erros) else 0
                t = a + e
                total_geral += t
                acc = (a / t * 100) if t > 0 else 0
                bar = "█" * int(acc/10) + "░" * (10-int(acc/10))
                print(f"   {h:<6} {a:<10.0f} {e:<10.0f} {t:<10.0f} {acc:<8.1f} {bar}")
            
            # Total geral
            acc_geral = (sum(n_acertos) / total_geral * 100) if total_geral > 0 else 0
            print(f"\n   📊 TOTAL: {total_geral:,.0f} trades | Acurácia média: {acc_geral:.1f}%")
            
            # Loss
            historico_loss = dados.get('historico_loss', [])
            if historico_loss:
                loss_inicial = historico_loss[0]
                loss_final = historico_loss[-1]
                loss_melhorou = loss_final < loss_inicial
                print(f"   📉 Loss: {loss_inicial:.4f} → {loss_final:.4f} ({'✅ melhorou' if loss_melhorou else '⚠️ piorou'})")
            
            # Estado interno
            estado = dados.get('estado_interno')
            if estado is not None:
                print(f"   🧬 Estado interno: {estado.shape}")
            
            # Optimizer & Scheduler
            tem_opt = 'optimizer_state_dict' in dados
            tem_sched = 'scheduler_state_dict' in dados
            print(f"   ⚡ Optimizer: {'✅' if tem_opt else '❌'} | Scheduler: {'✅' if tem_sched else '❌'}")
            
            # ACURÁCIA REAL (dos JSONs de verificação)
            vrf_file = vrf_path / f"{nome}.json"
            if vrf_file.exists():
                with open(vrf_file) as f:
                    vrf = json.load(f)
                
                print(f"\n   ✅ ACURÁCIA REAL (verificada):")
                print(f"   {'Horiz.':<6} {'Acertos':<10} {'Erros':<10} {'Total':<10} {'Acc %':<8} {'Barra'}")
                print(f"   {'-'*55}")
                
                for h in ['5','15','30','60','300','900','1800','3600']:
                    if h in vrf:
                        v = vrf[h]
                        t = v['total']
                        if t > 0:
                            acc = v['acertos'] / t * 100
                            bar = "█" * int(acc/10) + "░" * (10-int(acc/10))
                            print(f"   {horizontes[list(h_dict.keys()).index(h)] if h in h_dict else h+'s':<6} {v['acertos']:<10} {v['erros']:<10} {t:<10} {acc:<8.1f} {bar}")
                    else:
                        print(f"   {h+'s':<6} {'⌛ aguardando...'}")
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
    
    # Resumo final
    print(f"\n{'='*70}")
    print(f"📁 Total de mentes: {len(arquivos)}")
    print(f"📁 Pasta: {pt_path.absolute()}")
    print(f"{'='*70}")

h_dict = {'5':0,'15':1,'30':2,'60':3,'300':4,'900':5,'1800':6,'3600':7,'18000':8,'86400':9}

if __name__ == "__main__":
    inspecionar_mentes()