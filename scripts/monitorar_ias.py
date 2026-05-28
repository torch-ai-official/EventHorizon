# scripts/estudar_ias.py
import torch
import os
import json
from datetime import datetime

def estudar_todas_ias():
    """Analisa todas as IAs INSANA salvas"""
    
    print("="*70)
    print("📚 ESTUDO COMPLETO DAS IAS INSANA")
    print("="*70)
    print(f"Data da análise: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    pt_path = "data/mentes_pytorch"
    if not os.path.exists(pt_path):
        print("❌ Nenhuma mente INSANA encontrada!")
        return
    
    # Lista todos os arquivos .pt
    arquivos = [f for f in os.listdir(pt_path) if f.endswith(".pt")]
    
    if not arquivos:
        print("❌ Nenhum arquivo .pt encontrado!")
        return
    
    print(f"\n📊 Total de IAs encontradas: {len(arquivos)}\n")
    
    # Coleta dados de todas as IAs
    todas_ias = []
    
    for arquivo in sorted(arquivos):
        caminho = os.path.join(pt_path, arquivo)
        
        try:
            dados = torch.load(caminho, map_location='cpu')
            
            n_acertos = dados.get('n_acertos', [0,0,0,0])
            n_erros = dados.get('n_erros', [0,0,0,0])
            geracao = dados.get('geracao', 0)
            
            # Calcula acurácia por horizonte
            acc_5s = (n_acertos[0] / (n_acertos[0] + n_erros[0]) * 100) if (n_acertos[0] + n_erros[0]) > 0 else 0
            acc_15s = (n_acertos[1] / (n_acertos[1] + n_erros[1]) * 100) if (n_acertos[1] + n_erros[1]) > 0 else 0
            acc_30s = (n_acertos[2] / (n_acertos[2] + n_erros[2]) * 100) if (n_acertos[2] + n_erros[2]) > 0 else 0
            acc_60s = (n_acertos[3] / (n_acertos[3] + n_erros[3]) * 100) if (n_acertos[3] + n_erros[3]) > 0 else 0
            
            acc_media = (acc_5s + acc_15s + acc_30s + acc_60s) / 4
            
            # Determina a qual moeda pertence (se souber o mapeamento)
            # Você pode criar um arquivo de mapeamento separado
            moeda = "desconhecida"
            
            todas_ias.append({
                "arquivo": arquivo,
                "id": arquivo.replace("mente_", "").replace(".pt", ""),
                "moeda": moeda,
                "geracao": geracao,
                "acertos": n_acertos,
                "erros": n_erros,
                "acc_5s": acc_5s,
                "acc_15s": acc_15s,
                "acc_30s": acc_30s,
                "acc_60s": acc_60s,
                "acc_media": acc_media
            })
            
        except Exception as e:
            print(f"❌ Erro ao ler {arquivo}: {e}")
    
    # Ordena por acurácia média (melhores primeiro)
    todas_ias.sort(key=lambda x: x["acc_media"], reverse=True)
    
    # ============================================================
    # RELATÓRIO DETALHADO
    # ============================================================
    
    print("\n" + "="*70)
    print("🏆 RANKING DAS IAS (MELHORES PRIMEIRO)")
    print("="*70)
    
    for i, ia in enumerate(todas_ias, 1):
        medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        
        # Define status baseado na acurácia média
        if ia["acc_media"] >= 80:
            status = "🔥 INSANA"
        elif ia["acc_media"] >= 60:
            status = "🚀 BOA"
        elif ia["acc_media"] >= 45:
            status = "📈 APRENDENDO"
        else:
            status = "⚠️ INICIANDO"
        
        print(f"\n{medalha} #{i} - {ia['arquivo']}")
        print(f"   📊 Acurácia média: {ia['acc_media']:.1f}% ({status})")
        print(f"   📈 Geração: {ia['geracao']}")
        print(f"   ⏱️  5s:  {ia['acc_5s']:.1f}%  ({ia['acertos'][0]:.1f}/{ia['acertos'][0]+ia['erros'][0]:.1f})")
        print(f"   ⏱️  15s: {ia['acc_15s']:.1f}%  ({ia['acertos'][1]:.1f}/{ia['acertos'][1]+ia['erros'][1]:.1f})")
        print(f"   ⏱️  30s: {ia['acc_30s']:.1f}%  ({ia['acertos'][2]:.1f}/{ia['acertos'][2]+ia['erros'][2]:.1f})")
        print(f"   ⏱️  60s: {ia['acc_60s']:.1f}%  ({ia['acertos'][3]:.1f}/{ia['acertos'][3]+ia['erros'][3]:.1f})")
    
    # ============================================================
    # ESTATÍSTICAS GERAIS
    # ============================================================
    
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS GERAIS")
    print("="*70)
    
    ias_validas = [ia for ia in todas_ias if ia["acc_media"] > 0]
    
    if ias_validas:
        melhor_ia = max(ias_validas, key=lambda x: x["acc_media"])
        pior_ia = min(ias_validas, key=lambda x: x["acc_media"])
        media_geral = sum(ia["acc_media"] for ia in ias_validas) / len(ias_validas)
        
        print(f"📈 Total de IAs: {len(todas_ias)}")
        print(f"🎯 IAs com aprendizado: {len(ias_validas)}")
        print(f"⭐ Média geral de acurácia: {media_geral:.1f}%")
        print(f"🏆 Melhor IA: {melhor_ia['arquivo']} ({melhor_ia['acc_media']:.1f}%)")
        print(f"📉 Pior IA: {pior_ia['arquivo']} ({pior_ia['acc_media']:.1f}%)")
    
    # ============================================================
    # EXPORTAR COMO JSON
    # ============================================================
    
    # Salva relatório em JSON
    relatorio = {
        "data_analise": datetime.now().isoformat(),
        "total_ias": len(todas_ias),
        "ranking": todas_ias,
        "estatisticas": {
            "media_geral": media_geral if ias_validas else 0,
            "melhor_ia": melhor_ia["arquivo"] if ias_validas else None,
            "melhor_acuracia": melhor_ia["acc_media"] if ias_validas else 0
        }
    }
    
    with open("relatorio_ias.json", "w") as f:
        json.dump(relatorio, f, indent=2)
    
    print("\n" + "="*70)
    print(f"💾 Relatório salvo em: relatorio_ias.json")
    print("="*70)
    
    # ============================================================
    # EXPORTAR MELHORES IAS
    # ============================================================
    
    print("\n🚀 MELHORES IAS PARA EXPORTAR (versão Enterprise):")
    print("-"*50)
    
    top_ias = [ia for ia in todas_ias if ia["acc_media"] >= 80]
    if top_ias:
        for ia in top_ias[:5]:
            print(f"   ✅ {ia['arquivo']} - {ia['acc_media']:.1f}%")
    else:
        print("   ⚠️ Nenhuma IA com acurácia >= 80% ainda")

if __name__ == "__main__":
    estudar_todas_ias()