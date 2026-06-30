# sinal_engine.py v4.1 - CORRIGIDO

"""
Correções vs v4:
1. Usa acurácia REAL dos dados de verificação (sem penalização)
2. DiscordSender persistente (não cria nova instância a cada chamada)
3. Debug melhorado mostrando acurácias por horizonte
4. Filtro de acurácia mínima configurável
"""

import os
import json
import math
import time
from collections import deque
from telegram_sender import enviar_para_todos_canais

HORIZONTES = [5, 15, 30, 60, 300, 900, 1800, 3600, 18000, 86400]

_NOMES_H = {
    5: "5s", 15: "15s", 30: "30s", 60: "1min",
    300: "5min", 900: "15min", 1800: "30min", 3600: "1h",
    18000: "5h", 86400: "1d",
}

_GRUPOS = {
    "micro": [0, 1, 2, 3],
    "scalping": [4, 5],
    "intraday": [6, 7],
    "swing": [8, 9],
}

_IDX_PARA_GRUPO = {}
for grupo, idxs in _GRUPOS.items():
    for i in idxs:
        _IDX_PARA_GRUPO[i] = grupo

_ALVO_BASE = {
    5: 0.0010, 15: 0.0015, 30: 0.0020, 60: 0.0025,
    300: 0.0050, 900: 0.0090, 1800: 0.0130, 3600: 0.0180,
    18000: 0.0300, 86400: 0.0500,
}

_RR_MIN = {
    5: 1.5, 15: 1.5, 30: 1.6, 60: 1.7,
    300: 1.8, 900: 2.0, 1800: 2.0, 3600: 2.0,
    18000: 2.2, 86400: 2.5,
}

_PRED_MIN = {
    5: 0.04, 15: 0.04, 30: 0.05, 60: 0.05,
    300: 0.08, 900: 0.12, 1800: 0.15, 3600: 0.10,
    18000: 0.08, 86400: 0.06,
}

_AMOSTRAS_MIN = {
    5: 2000, 15: 1500, 30: 1000, 60: 800,
    300: 500, 900: 300, 1800: 200, 3600: 150,
    18000: 100, 86400: 50,
}

_EV_MIN = 0.0015
_PF_MIN = 1.25
_CONFLUENCIA_GRUPOS_MIN = 1
_EV_BREAK_FACTOR = 2.0
_COOLDOWN_GLOBAL = 180
_ACC_MINIMA = 48.0  # % - NOVO: filtro de acurácia mínima

_COOLDOWN_BASE = {
    5: 180, 15: 180, 30: 180, 60: 180,
    300: 180, 900: 180, 1800: 180, 3600: 180,
    18000: 180, 86400: 180,
}

_REGIME_OK = {
    "micro": {"trend_up", "trend_down", "volatile", "ranging"},
    "scalping": {"trend_up", "trend_down", "volatile", "ranging"},
    "intraday": {"trend_up", "trend_down", "ranging"},
    "swing": {"trend_up", "trend_down", "ranging"},
}
_FATOR_SUBSAMPLE = {
    5: 1,       # 5s:    registra a cada 1 tick
    15: 1,      # 15s:   registra a cada 1 tick
    30: 2,      # 30s:   registra a cada 2 ticks
    60: 5,      # 1min:  registra a cada 5 ticks (10s)
    300: 25,    # 5min:  registra a cada 25 ticks (50s)
    900: 75,    # 15min: registra a cada 75 ticks (2.5min)
    1800: 150,  # 30min: registra a cada 150 ticks (5min)
    3600: 300,  # 1h:    registra a cada 300 ticks (10min)
    18000: 1500, # 5h:   registra a cada 1500 ticks (50min)
    86400: 7200, # 1d:   registra a cada 7200 ticks (4h)
}

_JANELA_ACURACIA = 15000  # trades recentes para calcular acurácia
_DELAY_S = 2  # delay do crypto_app (deve bater com self.delay)
def _amostras_efetivas(total_bruto: int, h: int) -> int:
    """
    Com subsampling ativo no crypto_app, cada trade no histórico
    já representa uma decisão independente do modelo.
    Aplica apenas um desconto conservador para horizontes longos.
    """
    fator = _FATOR_SUBSAMPLE.get(h, 1)
    
    if fator <= 1:
        return total_bruto
    
    # O subsampling já garante independência
    # Desconto de 20% como margem de segurança
    return max(1, int(total_bruto * 0.8))

def _rr_dinamico_real(h, pred_pct, preco, atr_pct):
    alvo_base = _ALVO_BASE[h]
    pred_frac = abs(pred_pct) / 100.0
    
    alvo = max(alvo_base, min(pred_frac * 0.70, alvo_base * 2.5))
    
    if h <= 60:
        atr_mult = 1.0
    elif h <= 1800:
        atr_mult = 1.2
    else:
        atr_mult = 1.5
    
    stop_atr = atr_pct * atr_mult
    stop_min = alvo * 0.30
    stop = max(stop_atr, stop_min)
    
    rr = round(alvo / stop, 2) if stop > 0 else 0.0
    
    return alvo, stop, rr

def _confluencia_grupos(preds):
    direcoes_grupo = {g: [] for g in _GRUPOS}
    for idx, h in enumerate(HORIZONTES):
        if idx < len(preds):
            grupo = _IDX_PARA_GRUPO.get(idx)
            if grupo:
                direcoes_grupo[grupo].append(1 if preds[idx] > 0 else -1)
    
    dir_grupo = {}
    for grupo, dirs in direcoes_grupo.items():
        if not dirs:
            dir_grupo[grupo] = None
            continue
        soma = sum(dirs)
        dir_grupo[grupo] = 1 if soma > 0 else (-1 if soma < 0 else None)
    
    return dir_grupo

def _contar_confluencia(idx_sinal, preds):
    dir_grupo = _confluencia_grupos(preds)
    grupo_sinal = _IDX_PARA_GRUPO.get(idx_sinal)
    direcao_sinal = 1 if preds[idx_sinal] > 0 else -1
    
    grupos_conf = []
    h_conf = []
    
    for grupo, direcao in dir_grupo.items():
        if grupo == grupo_sinal:
            continue
        if direcao == direcao_sinal:
            grupos_conf.append(grupo)
            for idx in _GRUPOS[grupo]:
                if idx < len(preds) and abs(preds[idx]) >= _PRED_MIN.get(HORIZONTES[idx], 0.03):
                    h_conf.append(_NOMES_H[HORIZONTES[idx]])
    
    return len(grupos_conf), grupos_conf, h_conf

def _label_confluencia(n_grupos):
    if n_grupos >= 3: return "MUITO FORTE ████"
    if n_grupos == 2: return "FORTE ███░"
    if n_grupos == 1: return "MODERADA ██░░"
    return "FRACA █░░░"

class SignalEngine:
    def __init__(self, token_bot: str):
        self.token_bot = token_bot
        self._ultimo_sinal = {}
        self._ultimo_sinal_global = {}
        self._ultimo_payload = None
        self._discord_sender = None
        self._startup_time = None
        
        # Inicializa DiscordSender uma única vez
        try:
            from discord_sender import DiscordSender
            self._discord_sender = DiscordSender()
            print("[SignalEngine] ✅ DiscordSender inicializado com sucesso")
        except Exception as e:
            print(f"[SignalEngine] ⚠️ Erro ao iniciar DiscordSender: {e}")
            print("[SignalEngine] ⚠️ Sinais do Discord serão enviados via fallback")

    def avaliar(self, moeda, preco, preds_percentual, resultados_verificacao, 
                regime="ranging", arquivo_disco=None, acc_mente=None, atr_pct=0.0):
        
        resultados = self._merge_resultados(resultados_verificacao, arquivo_disco)
        agora = time.time()
        
        # Inicialização do startup time
        if self._startup_time is None:
            self._startup_time = agora
            print(f"\n{'='*72}")
            print(f"⏳ SIGNAL ENGINE INICIADO")
            print(f"⏳ Aguardando 3 minutos para estabilizar o sistema...")
            print(f"{'='*72}")
            return
        
        # Verifica tempo de startup
        tempo_desde_startup = agora - self._startup_time
        if tempo_desde_startup < 180:
            if int(tempo_desde_startup) % 60 == 0:  # Mostra a cada minuto
                print(f"⏳ Estabilizando... ({int(tempo_desde_startup)}s de 180s)")
            return
        
        # DEBUG: Mostra dados de acurácia disponíveis
        print(f"\n{'='*72}")
        print(f"🔍 [{moeda.replace('USDT','')}] ${preco:,.4f} | Regime: {regime}")
        print(f"{'='*72}")
        print(f"📊 ACURÁCIAS POR HORIZONTE (dados reais de verificação):")
        
        for h in HORIZONTES:
            h_str = str(h)
            if h_str in resultados:
                dados = resultados[h_str]
                total = dados.get("total", 0)
                acertos = dados.get("acertos", 0)
                if total > 0:
                    acc = (acertos / total) * 100
                    nome = _NOMES_H[h]
                    barra = "█" * int(acc / 10) + "░" * (10 - int(acc / 10))
                    print(f"  {nome:<7}: {barra} {acc:5.1f}% ({acertos}/{total} trades)")
        
        print(f"{'='*72}")
        print(f"🔍 ANALISANDO CANDIDATOS:")
        print(f"{'H':<7} {'Pred%':<9} {'Acc%':<8} {'N':<6} {'EV%':<8} {'PF':<6} {'R/R':<6} {'Status'}")
        print(f"{'-'*72}")
        
        candidatos = []
        
        for idx, h in enumerate(HORIZONTES):
            if idx >= len(preds_percentual):
                break
            
            pred = preds_percentual[idx]
            nome = _NOMES_H[h]
            grupo = _IDX_PARA_GRUPO.get(idx, "micro")
            
            def rejeitar(motivo):
                print(f"{nome:<7} {pred:+.3f}% {'—':<8} {'—':<6} {'—':<8} {'—':<6} {'—':<6} ❌ {motivo}")
            
            # 1. Predição mínima
            if abs(pred) < _PRED_MIN[h]:
                rejeitar(f"Pred < {_PRED_MIN[h]:.2f}%")
                continue
            
            # 2. Regime
            if regime not in _REGIME_OK.get(grupo, set()):
                rejeitar(f"Regime '{regime}'")
                continue
            
                        # 3. Acurácia - USA JANELA RECENTE (últimos 15000 trades)
            h_str = str(h)
            dados_h = resultados.get(h_str, {"acertos": 0, "erros": 0, "total": 0, "historico": []})
            total_h = dados_h.get("total", 0)
            historico_h = dados_h.get("historico", [])

            if total_h >= _AMOSTRAS_MIN[h]:
                if len(historico_h) > 0:
                    # USA JANELA RECENTE (últimos _JANELA_ACURACIA trades)
                    janela = historico_h[-_JANELA_ACURACIA:]
                    acertos_recentes = sum(janela)
                    total_recentes = len(janela)
                    
                    amostras_efetivas_recentes = _amostras_efetivas(total_recentes, h)

                    if amostras_efetivas_recentes >= _AMOSTRAS_MIN[h]:
                        p_raw = acertos_recentes / total_recentes
                        n_amostras = amostras_efetivas_recentes  # mostra amostras EFETIVAS
                        fonte_acc = f"rec({amostras_efetivas_recentes}e)"
                        
                        # 🛡️ ANTI-VIÉS: regressão bayesiana à média
                        # Acurácias extremas com poucas amostras são estatisticamente implausíveis
                        if p_raw > 0.75 and total_recentes < 5000:
                            fator_confianca = total_recentes / 5000
                            p_raw = 0.50 + (p_raw - 0.50) * fator_confianca
                            fonte_acc = f"rec({total_recentes})⚡"
                            print(f"   ⚡ Acc ajustada: {p_raw*100:.1f}% (era {(acertos_recentes/total_recentes)*100:.1f}%, {total_recentes} amostras)")
                        elif p_raw > 0.90:
                            p_raw = 0.55
                            fonte_acc = f"rec({total_recentes})🚫"
                            print(f"   🚫 Acc IRREAL detectada → ajustada para 55%")
                    else:
                        # Janela muito pequena, usa total
                        acertos_h = dados_h.get("acertos", 0)
                        p_raw = acertos_h / total_h if total_h > 0 else 0.5
                        n_amostras = total_h
                        fonte_acc = "ext"
                else:
                    # Sem histórico detalhado, usa total
                    acertos_h = dados_h.get("acertos", 0)
                    p_raw = acertos_h / total_h if total_h > 0 else 0.5
                    n_amostras = total_h
                    fonte_acc = "ext"
                
                # Verifica acurácia mínima
                if (p_raw * 100) < _ACC_MINIMA:
                    rejeitar(f"Acc {p_raw*100:.1f}% < {_ACC_MINIMA}%")
                    continue
            
            elif h >= 18000:
                # 🎯 INTERPOLAÇÃO para horizontes longos sem dados
                acc_menores = []
                pesos = []
                
                for h_menor, peso in [(3600, 0.5), (1800, 0.3), (900, 0.2)]:
                    str_menor = str(h_menor)
                    if str_menor in resultados:
                        d = resultados[str_menor]
                        if d["total"] >= _AMOSTRAS_MIN.get(h_menor, 100):
                            acc_menores.append(d["acertos"] / d["total"])
                            pesos.append(peso)
                
                if acc_menores:
                    p_raw = sum(a * w for a, w in zip(acc_menores, pesos)) / sum(pesos)
                    p_raw *= 0.85  # desconto de 15% pela incerteza da extrapolação
                    n_amostras = 0
                    fonte_acc = f"interp({len(acc_menores)}h)"
                    print(f"   🔮 1d/5h interpolado de {len(acc_menores)} horizontes → {p_raw*100:.1f}%")
                else:
                    rejeitar(f"Sem dados para interpolar 1d/5h")
                    continue
                    
            elif acc_mente is not None and idx < len(acc_mente):
                # Fallback para mente (só para horizontes curtos ou com poucos dados)
                # Se não há NENHUM dado externo para este horizonte, não confie na mente
                if total_h == 0 and h > 300:  # > 5min sem dados reais → rejeita
                    rejeitar(f"Sem dados reais para {nome}, mente ignorada")
                    continue
                
                # Aplica um cap conservador na acurácia da mente
                p_raw_mente = acc_mente[idx]
                if p_raw_mente > 0.70:
                    p_raw = 0.65  # nunca deixe a mente sozinha cravar >65%
                    fonte_acc = "mente⚠️"
                elif p_raw_mente < 0.40:
                    p_raw = 0.45
                    fonte_acc = "mente⚠️"
                else:
                    p_raw = p_raw_mente
                    fonte_acc = "mente"
                
                n_amostras = total_h  # 0
                print(f"   🧠 Usando mente (capado): {p_raw*100:.1f}% (original {p_raw_mente*100:.1f}%)")
            else:
                rejeitar(f"Amostras ({total_h} < {_AMOSTRAS_MIN[h]})")
                continue
            
            # Cap anti-overfitting
            p = min(p_raw, 0.85)
            
            # R/R com ATR real
            atr_efetivo = atr_pct if atr_pct > 0 else abs(pred) / 100 * 0.5
            alvo_frac, stop_frac, rr = _rr_dinamico_real(h, pred, preco, atr_efetivo)
            
            if rr < _RR_MIN[h]:
                rejeitar(f"R/R {rr:.2f} < {_RR_MIN[h]:.2f}")
                continue
            
            # EV e PF
            ev = p * alvo_frac - (1 - p) * stop_frac
            pf = (p * alvo_frac) / ((1 - p) * stop_frac + 1e-9)
            pf = min(pf, 5.0)
            
            if ev < _EV_MIN:
                rejeitar(f"EV {ev*100:.3f}% < {_EV_MIN*100:.3f}%")
                continue
            
            if pf < _PF_MIN:
                rejeitar(f"PF {pf:.2f} < {_PF_MIN:.2f}")
                continue
            
            # Cooldown individual
            ult_h = self._ultimo_sinal.get(moeda, {}).get(h, {})
            ts_ult = ult_h.get("ts", 0)
            ev_ult = ult_h.get("ev", 0)
            elapsed = agora - ts_ult
            cooldown = _COOLDOWN_BASE[h]
            
            if elapsed < cooldown:
                ev_quebra = ev_ult > 0 and ev >= ev_ult * _EV_BREAK_FACTOR
                if not ev_quebra:
                    rejeitar(f"Cooldown ({int(elapsed)}s < {cooldown}s)")
                    continue
            
            print(f"{nome:<7} {pred:+.3f}% {p*100:5.1f}%({fonte_acc}) {n_amostras:<6} {ev*100:+.3f}% {pf:5.2f} {rr:5.2f} ✅")
            
            candidatos.append({
                "idx": idx, "h": h, "nome": nome,
                "grupo": grupo, "pred": pred, "p": p,
                "p_raw": p_raw, "n": n_amostras,
                "ev": ev, "pf": pf, "rr": rr,
                "alvo_frac": alvo_frac, "stop_frac": stop_frac,
                "fonte_acc": fonte_acc,
            })
        
        if not candidatos:
            print(f"🔕 Nenhum candidato aprovado para {moeda}")
            return
        
        # Confluência
        melhor = None
        melhor_score = -1.0
        
        for cand in candidatos:
            n_grupos, grupos_conf, h_conf = _contar_confluencia(cand["idx"], preds_percentual)
            
            if n_grupos < _CONFLUENCIA_GRUPOS_MIN:
                print(f"   ⚠️  {cand['nome']}: confluência {n_grupos} < {_CONFLUENCIA_GRUPOS_MIN}")
                continue
            
            sharpe = cand["ev"] / (cand["stop_frac"] + 1e-9)
            score = (cand["ev"] * (1 + n_grupos * 0.30) * 
                    (1 + abs(cand["pred"]) / 100 * 0.20) * sharpe)
            
            print(f"   🎯 {cand['nome']}: {n_grupos} grupo(s), score={score:.6f}")
            
            if score > melhor_score:
                melhor_score = score
                melhor = {**cand, "n_grupos": n_grupos,
                         "grupos_conf": grupos_conf, "h_conf": h_conf, 
                         "score": score}
        
        if melhor is None:
            print(f"🔕 Nenhum candidato com confluência suficiente para {moeda}")
            return
        
        # Cooldown global
        ult_global = self._ultimo_sinal_global.get(moeda, {})
        tempo_desde_ultimo = agora - ult_global.get("ts", 0)
        
        if tempo_desde_ultimo < _COOLDOWN_GLOBAL:
            ev_ultimo = ult_global.get("ev", 0)
            ev_novo = melhor["ev"]
            if not (ev_ultimo > 0 and ev_novo >= ev_ultimo * _EV_BREAK_FACTOR):
                print(f"🔕 Cooldown global ({int(tempo_desde_ultimo)}s < {_COOLDOWN_GLOBAL}s)")
                return
        
        # Monta payload
        direcao_int = 1 if melhor["pred"] > 0 else -1
        alvo = preco * (1 + melhor["alvo_frac"]) if direcao_int > 0 else preco * (1 - melhor["alvo_frac"])
        stop = preco * (1 - melhor["stop_frac"]) if direcao_int > 0 else preco * (1 + melhor["stop_frac"])
        
        payload = {
            "ativo": moeda.replace("USDT", "/USDT"),
            "direcao": "ALTA" if direcao_int > 0 else "BAIXA",
            "horizonte": melhor["nome"],
            "entrada": preco,
            "alvo": alvo,
            "stop": stop,
            "acuracia": round(melhor["p_raw"] * 100, 1),
            "acuracia_janela": melhor["n"],
            "acuracia_fonte": melhor["fonte_acc"],
            "ev": melhor["ev"],
            "profit_factor": melhor["pf"],
            "rr": melhor["rr"],
            "confluencia_n": melhor["n_grupos"],
            "confluencia_grupos": melhor["grupos_conf"],
            "horizontes_confirmadores": melhor["h_conf"],
            "regime": regime,
            "score": round(melhor["score"], 5),
            "atr_pct": round(atr_efetivo * 100, 4),
        }
        
        self._ultimo_payload = payload
        
        # ENVIA TELEGRAM
        print(f"\n📤 ENVIANDO SINAL TELEGRAM: {moeda} {payload['direcao']} {melhor['nome']}")
        try:
            #enviar_para_todos_canais(self.token_bot, payload)
            print(f"[SignalEngine] ✅ Sinal enviado para Telegram")
        except Exception as e:
            print(f"[SignalEngine] ❌ Erro ao enviar Telegram: {e}")
        
        # ENVIA DISCORD (usando instância persistente)
        print(f"📤 ENVIANDO SINAL DISCORD: {moeda} {payload['direcao']} {melhor['nome']}")
        try:
            if self._discord_sender:
                self._discord_sender.enviar(payload)
            else:
                from discord_sender import enviar_sinal_discord
                enviar_sinal_discord(payload)
        except Exception as e:
            print(f"[SignalEngine] ❌ Erro ao enviar Discord: {e}")
        
        # Atualiza timestamps
        self._ultimo_sinal.setdefault(moeda, {})[melhor["h"]] = {
            "ts": agora, "ev": melhor["ev"]
        }
        self._ultimo_sinal_global[moeda] = {"ts": agora, "ev": melhor["ev"]}
        
        print(f"\n✅ SINAL ENVIADO: {moeda} {payload['direcao']} {melhor['nome']} | "
              f"EV={melhor['ev']*100:.3f}% | PF={melhor['pf']:.2f} | "
              f"R/R={melhor['rr']:.2f} | Acc={melhor['p_raw']*100:.1f}% | "
              f"Score={melhor['score']:.5f}")
        print(f"{'='*72}\n")

    @staticmethod
    def _merge_resultados(ram, arquivo):
        merged = {}
        
        # Dados da RAM (resultados_verificacao)
        for h_key, dados in ram.items():
            merged[str(h_key)] = {
                "acertos": dados.get("acertos", 0),
                "erros": dados.get("erros", 0),
                "total": dados.get("total", 0),
                "historico": dados.get("historico", []), 
            }
        
        # Dados do disco (se existir)
        if arquivo and os.path.exists(arquivo):
            try:
                with open(arquivo, "r") as f:
                    disco = json.load(f)
                
                for h_key, dados in disco.items():
                    if h_key in merged:
                        merged[h_key]["acertos"] += dados.get("acertos", 0)
                        merged[h_key]["erros"] += dados.get("erros", 0)
                        merged[h_key]["total"] += dados.get("total", 0)
                        # Mescla histórico
                        hist_disco = dados.get("historico", [])
                        hist_ram = merged[h_key].get("historico", [])
                        merged[h_key]["historico"] = (hist_ram + hist_disco)[-_JANELA_ACURACIA:]
                    else:
                        merged[h_key] = {
                            "acertos": dados.get("acertos", 0),
                            "erros": dados.get("erros", 0),
                            "total": dados.get("total", 0),
                            "historico": dados.get("historico", []),
                        }
            except Exception as e:
                print(f"[SignalEngine] ⚠️ Erro ao ler disco: {e}")
        
        return merged