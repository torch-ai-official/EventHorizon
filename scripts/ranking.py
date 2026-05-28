# scripts/ranking.py
import os
import sqlite3
import torch
from pathlib import Path

def get_ranking_por_sql(limite=20):
    """Ranking baseado no SQL (histórico de performance)"""
    conn = sqlite3.connect("data/mentes.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        WHERE symbol IS NOT NULL AND symbol != ''
        GROUP BY symbol
        HAVING total > 10
        ORDER BY acuracia DESC
        LIMIT ?
    """, (limite,))
    
    resultados = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*70)
    print("🏆 RANKING DE MOEDAS (BASEADO NO SQL)")
    print("="*70)
    print(f"{'MOEDA':<12} {'TOTAL':<8} {'ACERTOS':<8} {'ACURACIA':<10} {'STATUS':<15}")
    print("-"*70)
    
    for symbol, total, acertos, acuracia in resultados:
        status = "🔥 RECOMENDADA" if acuracia >= 55 else "📈 APRENDENDO" if acuracia >= 45 else "⚠️ BAIXA"
        print(f"{symbol:<12} {total:<8} {acertos:<8} {acuracia:<9.1f}% {status}")
    
    return resultados

def get_ranking_por_pt(limite=20):
    """Ranking baseado nos arquivos .pt (pesos das IAs)"""
    pt_path = Path("data/mentes_pytorch")
    if not pt_path.exists():
        print("\n⚠️ Nenhum arquivo .pt encontrado")
        return []
    
    ranking = []
    
    for arquivo in pt_path.glob("*.pt"):
        try:
            dados = torch.load(arquivo, map_location='cpu')
            
            # Pega acertos e erros (suporta tanto lista quanto int)
            acertos = dados.get('n_acertos', [0])
            erros = dados.get('n_erros', [0])
            
            if isinstance(acertos, list):
                acertos_5s = acertos[0] if len(acertos) > 0 else 0
                erros_5s = erros[0] if len(erros) > 0 else 0
            else:
                acertos_5s = acertos
                erros_5s = erros
            
            total = acertos_5s + erros_5s
            acuracia = (acertos_5s / total * 100) if total > 0 else 0
            
            # Tenta identificar qual moeda é baseado no ID
            # (você pode melhorar isso mapeando ID -> symbol)
            ranking.append({
                "arquivo": arquivo.stem,
                "acertos": acertos_5s,
                "erros": erros_5s,
                "total": total,
                "acuracia": acuracia,
                "geracao": dados.get('geracao', 0)
            })
            
        except Exception as e:
            print(f"❌ Erro ao ler {arquivo}: {e}")
    
    ranking.sort(key=lambda x: x["acuracia"], reverse=True)
    
    print("\n" + "="*70)
    print("🏆 RANKING DE ARQUIVOS .PT (PESOS DAS IAs)")
    print("="*70)
    print(f"{'ARQUIVO':<25} {'ACERTOS':<8} {'TOTAL':<8} {'ACURACIA':<10} {'GERACAO':<10}")
    print("-"*70)
    
    for i, m in enumerate(ranking[:limite]):
        status_emoji = "🔥" if m["acuracia"] >= 55 else "📈" if m["acuracia"] >= 45 else "⚠️"
        print(f"{status_emoji} {m['arquivo']:<23} {m['acertos']:<8} {m['total']:<8} {m['acuracia']:<9.1f}% {m['geracao']:<10}")
    
    return ranking

def get_melhores_para_exportar(limite=5):
    """Retorna as melhores moedas para exportar (para vender)"""
    conn = sqlite3.connect("data/mentes.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
        WHERE symbol IS NOT NULL AND symbol != ''
        GROUP BY symbol
        HAVING total > 50
        ORDER BY acuracia DESC
        LIMIT ?
    """, (limite,))
    
    resultados = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*70)
    print("🚀 MOEDAS RECOMENDADAS PARA EXPORTAR (VERSÃO ENTERPRISE)")
    print("="*70)
    
    for symbol, total, acertos, acuracia in resultados:
        print(f"\n✅ {symbol}")
        print(f"   ├── Acurácia: {acuracia}%")
        print(f"   ├── Acertos: {acertos}/{total}")
        print(f"   └── Arquivo .pt: data/mentes_pytorch/{symbol}.pt")
    
    return resultados

def mostrar_estatisticas_gerais():
    """Mostra estatísticas gerais do sistema"""
    conn = sqlite3.connect("data/mentes.db")
    cursor = conn.cursor()
    
    # Total geral
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(acertou) as acertos,
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM performance
    """)
    total, acertos, acuracia = cursor.fetchone()
    
    # Por período
    cursor.execute("""
        SELECT 
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM (
            SELECT acertou FROM performance ORDER BY timestamp DESC LIMIT 100
        )
    """)
    ultimas_100 = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT 
            ROUND(SUM(acertou) * 100.0 / COUNT(*), 1) as acuracia
        FROM (
            SELECT acertou FROM performance ORDER BY timestamp DESC LIMIT 500
        )
    """)
    ultimas_500 = cursor.fetchone()[0] or 0
    
    conn.close()
    
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS GERAIS")
    print("="*70)
    print(f"📈 Acurácia Geral: {acuracia}% ({acertos}/{total})")
    print(f"🟢 Últimas 100 previsões: {ultimas_100}%")
    print(f"🟡 Últimas 500 previsões: {ultimas_500}%")
    print(f"{'🟢' if ultimas_500 > acuracia else '🔴'} Tendência: {'Melhorando' if ultimas_500 > acuracia else 'Piorando'}")

if __name__ == "__main__":
    print("\n🤖 ANALISANDO PERFORMANCE DA IA...\n")
    
    # 1. Ranking por SQL
    get_ranking_por_sql(20)
    
    # 2. Ranking por .pt
    get_ranking_por_pt(20)
    
    # 3. Melhores para exportar
    get_melhores_para_exportar(5)
    
    # 4. Estatísticas gerais
    mostrar_estatisticas_gerais()
    
    print("\n" + "="*70)
    print("💡 DICA: Para exportar as moedas, use:")
    print("   python scripts/exportar_moedas.py BTCUSDT ETHUSDT SOLUSDT")
    print("="*70 + "\n")