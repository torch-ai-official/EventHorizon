# atualizar_dashboard.py
import json
import os
import glob
import datetime
import subprocess

def gerar_dados_json():
    """Gera o dados.json com métricas REAIS do sistema"""
    
    dados = {
        "ultima_atualizacao": datetime.datetime.now().strftime("%d/%m %H:%M"),
        "performance": [],
        "total_trades": 0,
        "acuracia_geral": 0,
        "profit_factor": 0,
        "melhores_horizontes": 0
    }
    
    total_acertos_global = 0
    total_erros_global = 0
    
    # Lê todos os arquivos de verificação
    arquivos = glob.glob("data/verificacoes/*.json")
    
    for arquivo in arquivos:
        moeda = os.path.basename(arquivo).replace(".json", "")
        
        with open(arquivo) as f:
            vrf = json.load(f)
        
        perf = {
            "symbol": moeda.replace("USDT", ""),
            "total_trades": 0
        }
        
        for h_str, dados_h in vrf.items():
            if dados_h['total'] > 10:
                acertos = dados_h['acertos']
                erros = dados_h['erros']
                total = dados_h['total']
                acuracia = round(acertos / total * 100, 1)
                
                # Adiciona acurácia por horizonte
                h_int = int(h_str)
                perf[f"acuracia_{h_int}s"] = acuracia
                perf["total_trades"] += total
                
                total_acertos_global += acertos
                total_erros_global += erros
        
        if perf["total_trades"] > 0:
            dados["performance"].append(perf)
    
    # Ordena por total de trades
    dados["performance"].sort(key=lambda x: x["total_trades"], reverse=True)
    
    # Métricas globais
    total_global = total_acertos_global + total_erros_global
    if total_global > 0:
        dados["acuracia_geral"] = round(total_acertos_global / total_global * 100, 1)
        dados["profit_factor"] = round(total_acertos_global / total_erros_global, 2) if total_erros_global > 0 else 999
        dados["total_trades"] = total_global
        dados["melhores_horizontes"] = sum(1 for p in dados["performance"] if any(
            v for k, v in p.items() if k.startswith("acuracia_") and isinstance(v, (int, float)) and v > 50
        ))
    
    return dados


def atualizar_dashboard_github():
    """Gera dados.json e faz push pro GitHub"""
    
    print("\n📊 Gerando dados atualizados...")
    dados = gerar_dados_json()
    
    # Salva localmente
    caminho = "trader-ai/dados.json"
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    
    with open(caminho, "w") as f:
        json.dump(dados, f, indent=2)
    
    print(f"✅ dados.json gerado: {dados['total_trades']} trades, {dados['acuracia_geral']}% acurácia")
    
    # Faz commit e push
    try:
        os.chdir("trader-ai")
        subprocess.run(["git", "add", "dados.json"], check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {dados['ultima_atualizacao']} - {dados['acuracia_geral']}%"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Dashboard atualizado no GitHub Pages!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
    finally:
        os.chdir("..")


if __name__ == "__main__":
    atualizar_dashboard_github()