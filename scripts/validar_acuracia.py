# scripts/ver_aprendizado_ia.py - VERSÃO FINAL COM ACURÁCIA REAL
import torch
import os
import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def visualizar_aprendizado():
    """Visualiza como a IA INSANA aprendeu ao longo do tempo"""
    
    pt_path = Path("data/mentes_pytorch")
    arquivos = sorted(pt_path.glob("*.pt"))
    
    if not arquivos:
        print("Nenhuma IA INSANA encontrada!")
        return
    
    print("="*70)
    print("🧠 ANALISANDO INTELIGÊNCIA DA IA INSANA (10 HORIZONTES)")
    print("="*70)
    
    for i, arq in enumerate(arquivos):
        try:
            dados = torch.load(arq, map_location='cpu')
            geracao = dados.get('geracao', 0)
            n_acertos = dados.get('n_acertos', [0]*10)
            n_erros = dados.get('n_erros', [0]*10)
            total = sum(n_acertos) + sum(n_erros)
            acc_media = sum([a/(a+e)*100 if (a+e)>0 else 0 for a,e in zip(n_acertos, n_erros)]) / max(1, len(n_acertos))
            
            # Tenta carregar acurácia real
            moeda_nome = arq.stem.replace("mente_", "")
            vrf_file = Path(f"data/verificacoes/{moeda_nome}.json")
            tem_real = "✅" if vrf_file.exists() else "⏳"
            
            print(f"{i+1}. {arq.name} | {geracao} ger | {total:.0f} trades | Treino: {acc_media:.1f}% | Real: {tem_real}")
        except Exception as e:
            print(f"{i+1}. {arq.name} - ERRO: {e}")
    
    escolha = input("\n📊 Escolha a IA para analisar (número): ")
    idx = int(escolha) - 1
    arquivo = arquivos[idx]
    moeda_nome = arquivo.stem.replace("mente_", "")
    
    print(f"\n📊 Analisando {arquivo.name}...")
    
    # Carrega dados de treino
    dados = torch.load(arquivo, map_location='cpu')
    n_acertos = dados.get('n_acertos', [0]*10)
    n_erros = dados.get('n_erros', [0]*10)
    historico_loss = dados.get('historico_loss', [])
    geracao = dados.get('geracao', 0)
    
    # Carrega dados REAIS de verificação
    vrf_file = Path(f"data/verificacoes/{moeda_nome}.json")
    acuracias_reais = None
    if vrf_file.exists():
        with open(vrf_file) as f:
            vrf_data = json.load(f)
        acuracias_reais = []
        for h in ['5','15','30','60','300','900','1800','3600','18000','86400']:
            h_int = int(h)
            r = vrf_data.get(str(h_int), vrf_data.get(h_int, {"acertos":0,"erros":0,"total":0}))
            total = r["acertos"] + r["erros"]
            acc = (r["acertos"] / total * 100) if total > 0 else 0
            acuracias_reais.append(acc)
    
    HORIZONTES_NOMES = ['5s', '15s', '30s', '60s', '5m', '15m', '30m', '1h', '5h', '1d']
    
    # Acurácia de TREINO
    acuracias_treino = []
    for i in range(len(n_acertos)):
        total = n_acertos[i] + n_erros[i]
        acc = (n_acertos[i] / total * 100) if total > 0 else 0
        acuracias_treino.append(acc)
    
    # Cria visualização
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle(f'🧠 {moeda_nome} - Treino vs Real', fontsize=16, fontweight='bold')
    
    # Gráfico 1: Comparação TREINO vs REAL
    ax1 = axes[0, 0]
    x = np.arange(len(HORIZONTES_NOMES))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, acuracias_treino, width, label='Treino (próximo tick)', color='#f59e0b', alpha=0.8)
    if acuracias_reais:
        bars2 = ax1.bar(x + width/2, acuracias_reais, width, label='Real (horizonte)', color='#00e676', alpha=0.8)
    
    ax1.set_ylim(0, 105)
    ax1.set_ylabel('Acurácia (%)')
    ax1.set_title('🎯 Treino vs Real por Horizonte')
    ax1.set_xticks(x)
    ax1.set_xticklabels(HORIZONTES_NOMES, fontsize=7)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Gráfico 2: Loss
    ax2 = axes[0, 1]
    if historico_loss and len(historico_loss) > 1:
        ax2.plot(historico_loss, color='#ff3d57', linewidth=0.5, alpha=0.5)
        window = max(5, len(historico_loss) // 20)
        if len(historico_loss) > window:
            moving_avg = np.convolve(historico_loss, np.ones(window)/window, mode='valid')
            ax2.plot(range(window-1, len(historico_loss)), moving_avg, color='#00e676', linewidth=2, label=f'Média')
            ax2.legend()
        ax2.set_title('📉 Curva de Aprendizado')
        ax2.grid(True, alpha=0.3)
    
    # Gráfico 3: Radar comparativo
    ax3 = axes[0, 2]
    angles = np.linspace(0, 2 * np.pi, len(HORIZONTES_NOMES), endpoint=False).tolist()
    angles += angles[:1]
    
    treino_plot = acuracias_treino + acuracias_treino[:1]
    ax3.plot(angles, treino_plot, 'o-', linewidth=2, color='#f59e0b', label='Treino', alpha=0.8)
    ax3.fill(angles, treino_plot, alpha=0.1, color='#f59e0b')
    
    if acuracias_reais:
        real_plot = acuracias_reais + acuracias_reais[:1]
        ax3.plot(angles, real_plot, 'o-', linewidth=2, color='#00e676', label='Real', alpha=0.8)
        ax3.fill(angles, real_plot, alpha=0.1, color='#00e676')
    
    ax3.set_xticks(angles[:-1])
    ax3.set_xticklabels(HORIZONTES_NOMES, fontsize=7)
    ax3.set_ylim(0, 100)
    ax3.set_title('🎯 Radar: Treino vs Real')
    ax3.legend()
    ax3.grid(True)
    
    # Gráfico 4: Pizza
    ax4 = axes[1, 0]
    total_acertos = sum(n_acertos)
    total_erros = sum(n_erros)
    ax4.pie([total_acertos, total_erros], labels=['Acertos', 'Erros'], colors=['#00e676', '#ff3d57'],
            autopct='%1.1f%%', shadow=True, startangle=90, explode=(0.05, 0.05))
    ax4.set_title(f'📊 Treino: {total_acertos + total_erros:.0f} trades')
    
    # Gráfico 5: Barras agrupadas
    ax5 = axes[1, 1]
    x = np.arange(len(HORIZONTES_NOMES))
    width = 0.35
    ax5.bar(x - width/2, n_acertos, width, label='Acertos', color='#00e676', alpha=0.7)
    ax5.bar(x + width/2, n_erros, width, label='Erros', color='#ff3d57', alpha=0.7)
    ax5.set_xticks(x)
    ax5.set_xticklabels(HORIZONTES_NOMES, fontsize=7)
    ax5.set_title('📈 Distribuição Acertos/Erros (Treino)')
    ax5.legend()
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Gráfico 6: Acurácia Real (se disponível)
    ax6 = axes[1, 2]
    if acuracias_reais:
        cores_reais = ['#00e676' if a >= 55 else '#f59e0b' if a >= 45 else '#ff3d57' for a in acuracias_reais]
        ax6.bar(HORIZONTES_NOMES, acuracias_reais, color=cores_reais)
        ax6.set_ylim(0, 105)
        ax6.set_title('✅ Acurácia REAL (verificada)')
        ax6.tick_params(axis='x', rotation=45)
        ax6.grid(True, alpha=0.3, axis='y')
        for i, acc in enumerate(acuracias_reais):
            if acc > 0:
                ax6.text(i, acc + 1, f'{acc:.1f}%', ha='center', fontsize=7, fontweight='bold')
    else:
        ax6.text(0.5, 0.5, 'Sem dados reais ainda\nDeixe rodando por alguns minutos', 
                ha='center', va='center', transform=ax6.transAxes, fontsize=12)
        ax6.set_title('⏳ Aguardando dados reais...')
    
    plt.tight_layout()
    plt.show()
    
    # Estatísticas
    print("\n" + "="*70)
    print(f"🧠 ANÁLISE COMPLETA - {moeda_nome}")
    print("="*70)
    
    print(f"\n📊 TREINO (próximo tick):")
    print(f"   Gerações: {geracao}")
    print(f"   Total trades: {total_acertos + total_erros:.0f}")
    print(f"   Acurácia média: {sum(acuracias_treino)/len(acuracias_treino):.1f}%")
    
    if acuracias_reais:
        print(f"\n✅ REAL (horizonte verificado):")
        for i, h in enumerate(HORIZONTES_NOMES):
            if acuracias_reais[i] > 0:
                print(f"   {h:>5}: {acuracias_reais[i]:.1f}%")
            else:
                print(f"   {h:>5}: ⏳ aguardando...")
    
    # Score
    if acuracias_reais:
        reais_validas = [a for a in acuracias_reais[:4] if a > 0]  # Só micro tem dados
        if reais_validas:
            score_real = sum(reais_validas) / len(reais_validas)
            print(f"\n🧠 SCORE REAL (micro): {score_real:.1f}%")
    
    print(f"\n💡 RECOMENDAÇÃO:")
    if acuracias_reais and any(a > 60 for a in acuracias_reais[:4]):
        print(f"   ✅ Micro horizontes acima de 60% - FUNCIONANDO!")
    print(f"   ⏳ Deixe rodando para ver acurácia dos horizontes longos")

if __name__ == "__main__":
    visualizar_aprendizado()