# atualizar_dashboard.py
import json
import os
import glob
import datetime
import subprocess

def gerar_dados_json():
    dados = {
        "ultima_atualizacao": datetime.datetime.now().strftime("%d/%m %H:%M"),
        "performance": [],
        "total_trades": 0,
        "acuracia_geral": 0,
        "profit_factor": 0,
        "melhores_horizontes": 0
    }

    # Um JSON por janela — o dashboard vai buscar o certo via filtro
    dados_por_janela = {
        100:  {"performance": [], "total_trades": 0, "acuracia_geral": 0, "profit_factor": 0},
        500:  {"performance": [], "total_trades": 0, "acuracia_geral": 0, "profit_factor": 0},
        1000: {"performance": [], "total_trades": 0, "acuracia_geral": 0, "profit_factor": 0},
    }

    total_acertos_global = 0
    total_erros_global   = 0

    arquivos = glob.glob("data/verificacoes/*.json")

    for arquivo in arquivos:
        moeda = os.path.basename(arquivo).replace(".json", "")

        with open(arquivo) as f:
            vrf = json.load(f)

        # ── Acumulado ────────────────────────────────────────────────────
        perf = {"symbol": moeda.replace("USDT", ""), "total_trades": 0}

        for h_str, dados_h in vrf.items():
            if dados_h['total'] > 10:
                acertos = dados_h['acertos']
                erros   = dados_h['erros']
                total   = dados_h['total']
                acuracia = round(acertos / total * 100, 1)

                h_int = int(h_str)
                perf[f"acuracia_{h_int}s"] = acuracia
                perf["total_trades"] += total

                total_acertos_global += acertos
                total_erros_global   += erros

        if perf["total_trades"] > 0:
            dados["performance"].append(perf)

        # ── Janelas reais (historico item-a-item) ────────────────────────
        for janela_n, dados_janela in dados_por_janela.items():
            perf_janela = {"symbol": moeda.replace("USDT", ""), "total_trades": 0}

            for h_str, dados_h in vrf.items():
                historico = dados_h.get('historico', [])

                if len(historico) == 0:
                    # Fallback: sem histórico individual ainda, usa acumulado
                    total = dados_h['total']
                    if total < 10:
                        continue
                    acertos = dados_h['acertos']
                    ultimos = min(total, janela_n)
                    taxa = acertos / total
                    acuracia = round(taxa * 100, 1)
                    n_usado = ultimos
                else:
                    ultimos = historico[-janela_n:]   # últimos N reais
                    if len(ultimos) < 10:
                        continue
                    acuracia = round(sum(ultimos) / len(ultimos) * 100, 1)
                    n_usado  = len(ultimos)

                h_int = int(h_str)
                perf_janela[f"acuracia_{h_int}s"] = acuracia
                perf_janela["total_trades"] += n_usado

            if perf_janela["total_trades"] > 0:
                dados_janela["performance"].append(perf_janela)

    # Ordena
    dados["performance"].sort(key=lambda x: x["total_trades"], reverse=True)
    for dj in dados_por_janela.values():
        dj["performance"].sort(key=lambda x: x["total_trades"], reverse=True)

    # Métricas globais (acumulado)
    total_global = total_acertos_global + total_erros_global
    if total_global > 0:
        dados["acuracia_geral"]    = round(total_acertos_global / total_global * 100, 1)
        dados["profit_factor"]     = round(total_acertos_global / total_erros_global, 2) if total_erros_global > 0 else 999
        dados["total_trades"]      = total_global
        dados["melhores_horizontes"] = sum(
            1 for p in dados["performance"]
            if any(v for k, v in p.items() if k.startswith("acuracia_") and isinstance(v, (int, float)) and v > 50)
        )
        for dj in dados_por_janela.values():
            dj["acuracia_geral"] = dados["acuracia_geral"]
            dj["profit_factor"]  = dados["profit_factor"]
            dj["total_trades"]   = total_global

    return dados, dados_por_janela


def atualizar_dashboard_github():
    print("\n📊 Gerando dados atualizados...")
    dados, dados_por_janela = gerar_dados_json()   # ← agora retorna 2 valores

    base_path = "trader-ai"
    os.makedirs(base_path, exist_ok=True)

    # Acumulado (todos os trades)
    with open(f"{base_path}/dados.json", "w") as f:
        json.dump(dados, f, indent=2)

    # Janelas reais
    for n, conteudo in dados_por_janela.items():
        with open(f"{base_path}/dados_{n}.json", "w") as f:
            json.dump(conteudo, f, indent=2)

    print(f"✅ dados.json: {dados['total_trades']} trades, {dados['acuracia_geral']}% acurácia")
    for n in dados_por_janela:
        print(f"✅ dados_{n}.json gerado")

    try:
        os.chdir(base_path)
        arquivos_git = ["dados.json"] + [f"dados_{n}.json" for n in dados_por_janela]
        subprocess.run(["git", "add"] + arquivos_git, check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {dados['ultima_atualizacao']}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Dashboard atualizado no GitHub Pages!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
    finally:
        os.chdir("..")


if __name__ == "__main__":
    atualizar_dashboard_github()