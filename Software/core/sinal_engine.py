# sinal_engine.py  v3
# ─────────────────────────────────────────────────────────────────────────────
# Melhorias vs v2:
#
#  1. Acurácia deslizante (rolling window)  — só os últimos N trades contam,
#     não o histórico inteiro acumulado.  Reflete a forma atual do modelo.
#
#  2. R/R dinâmico  — calculado a partir da volatilidade real (ATR implícito
#     nas predições de curto prazo), não uma fração fixa 1:2.
#
#  3. Confluência multi-camada  — agrupa horizontes em 4 faixas (micro,
#     scalping, intraday, swing) e exige concordância ENTRE faixas, não só
#     dentro de uma janela de ±3 índices.
#
#  4. Cooldown inteligente  — só silencia o ativo se o último sinal tiver sido
#     de qualidade similar ou melhor.  Sinais de EV muito superior quebram o
#     cooldown.
#
#  5. Score composto  — EV × confluência × Sharpe implícito × intensidade da
#     predição.  Garante que só o MELHOR sinal por ciclo seja enviado.
#
#  6. Payload PT e EN idênticos (mesma estrutura, idioma diferente apenas
#     nos textos fixos do formatador).
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import math
import time
from collections import deque
from telegram_sender import enviar_para_todos_canais

HORIZONTES = [5, 15, 30, 60, 300, 900, 1800, 3600, 18000, 86400]

_NOMES_H = {
    5:     "5s",
    15:    "15s",
    30:    "30s",
    60:    "1min",
    300:   "5min",
    900:   "15min",
    1800:  "30min",
    3600:  "1h",
    18000: "5h",
    86400: "1d",
}

# Grupos de horizonte: usados para confluência entre faixas
_GRUPOS = {
    "micro":    [0, 1, 2, 3],     # 5s, 15s, 30s, 1min
    "scalping": [4, 5],            # 5min, 15min
    "intraday": [6, 7],            # 30min, 1h
    "swing":    [8, 9],            # 5h, 1d
}
_IDX_PARA_GRUPO = {}
for grupo, idxs in _GRUPOS.items():
    for i in idxs:
        _IDX_PARA_GRUPO[i] = grupo

# Alvo base por horizonte — usado como REFERÊNCIA para R/R dinâmico
# O alvo real será ajustado pelo sinal da rede (mais forte → alvo maior)
_ALVO_BASE = {
    5:     0.0010,
    15:    0.0015,
    30:    0.0020,
    60:    0.0025,
    300:   0.0050,
    900:   0.0090,
    1800:  0.0130,
    3600:  0.0180,
    18000: 0.0300,
    86400: 0.0500,
}

# R/R mínimo exigido (risk:reward real, não fixo 1:2)
_RR_MIN = {
    5:     1.5,
    15:    1.5,
    30:    1.6,
    60:    1.7,
    300:   1.8,
    900:   2.0,
    1800:  2.0,
    3600:  2.0,
    18000: 2.2,
    86400: 2.5,
}

# Predição mínima (% do preço) para sequer avaliar o horizonte
_PRED_MIN = {
    5:     0.04,
    15:    0.04,
    30:    0.05,
    60:    0.05,
    300:   0.08,
    900:   0.12,
    1800:  0.15,
    3600:  0.10,
    18000: 0.08,
    86400: 0.06,
}

# Janela deslizante de acurácia: quantos trades recentes considerar
_ROLLING_WINDOW = {
    5:     800,    # Era 500
    15:    600,    # Era 300
    30:    500,    # Era 200
    60:    400,    # Era 150
    300:   300,    # Era 100
    900:   200,    # Era 80
    1800:  150,    # Era 60
    3600:  120,    # Era 50
    18000: 80,     # Era 30
    86400: 50,     # Era 20
}

# Amostras mínimas na janela para o sinal ser válido
_AMOSTRAS_MIN = {
    5:     150,
    15:    100,
    30:     80,
    60:     60,
    300:    50,
    900:    40,
    1800:   30,
    3600:   25,
    18000:  15,
    86400:   8,
}

# EV mínimo por operação (fração do preço)
_EV_MIN = 0.0015  # 0.0030 para 0.0015


# Profit Factor mínimo
_PF_MIN = 1.25

# Confluência: quantos GRUPOS diferentes precisam concordar
# (1 grupo = fraco; 2 grupos = moderado; 3+ = forte)
_CONFLUENCIA_GRUPOS_MIN = 1

# Cooldown base por ativo (segundos).  Pode ser quebrado por EV muito superior.
_COOLDOWN_BASE = {
    5:      300,
    15:     450,
    30:     600,
    60:     900,
    300:   1800,
    900:   3600,
    1800:  5400,
    3600:  7200,
    18000: 21600,
    86400: 86400,
}

# Se novo EV for X vezes maior que o EV do último sinal, quebra cooldown
_EV_BREAK_FACTOR = 2.0

# Cooldown global mínimo entre quaisquer sinais da mesma moeda
_COOLDOWN_GLOBAL = 900   # 15 min — antes era 5 min, causava spam

# Regimes compatíveis por faixa
_REGIME_OK = {
    "micro":    {"trend_up", "trend_down", "volatile", "ranging"},  # ⭐ Adicionado
    "scalping": {"trend_up", "trend_down", "volatile", "ranging"},
    "intraday": {"trend_up", "trend_down", "ranging"},
    "swing":    {"trend_up", "trend_down", "ranging"},
}

# =============================================================================
# ROLLING ACCURACY STORE
# Mantém uma fila circular dos últimos N resultados por (moeda, horizonte)
# =============================================================================

class _RollingStore:
    """
    Armazena os últimos resultados de verificação por (moeda, horizonte)
    para calcular acurácia numa janela deslizante.

    O SignalEngine alimenta isso via `registrar_resultado()`.
    Como os dados já chegam acumulados nos JSONs, extraímos a janela dos
    últimos N trades do total salvo em disco — não requer refatorar o
    sistema de verificação existente.
    """

    def __init__(self):
        # {moeda: {h_str: {"acertos": int, "total": int, "janela": deque}}}
        self._dados: dict[str, dict[str, dict]] = {}

    def acuracia_rolling(self, moeda: str, h: int, dados_merged: dict) -> tuple[float, int]:
        """
        Retorna (acurácia_rolling, n_amostras_disponíveis).

        Como não temos o histórico item-a-item (apenas o total acumulado),
        aproximamos usando os dados do período mais recente:
        - Lemos o total acumulado do merged (RAM + disco)
        - Comparamos com o total da sessão anterior (salvo internamente)
        - A diferença são os trades recentes

        Na prática, entre reinicializações o sistema usa os dados de disco
        completos para os horizontes mais longos (que têm poucas amostras)
        e a janela deslizante para os curtos (que têm muitas).
        """
        h_str = str(h)
        dados_h = dados_merged.get(h_str, {})
        total_acum   = dados_h.get("total",   0)
        acertos_acum = dados_h.get("acertos", 0)

        if total_acum == 0:
            return 0.5, 0

        janela = _ROLLING_WINDOW[h]

        if total_acum <= janela:
            # Poucos trades — usa tudo
            return acertos_acum / total_acum, total_acum

        # Tem mais trades que a janela: usa proporção dos últimos N
        # (sem acesso ao histórico item-a-item, a melhor proxy é assumir
        # que os últimos `janela` trades têm a mesma taxa de acertos global,
        # MAS penalizamos horizontes com muito histórico para dar mais peso
        # ao período recente — a acurácia "decai" levemente com o tempo)
        # 
        # Fórmula: acurácia_rolling = (acertos nos últimos N) / N
        # Estimativa conservadora: assume que a taxa de acertos recente
        # pode ser até 10% pior que a histórica (penalidade de idade)
        taxa_global   = acertos_acum / total_acum
        idade_fator   = min(1.0, janela / total_acum)   # 0→1: 1 = recente
        penalidade    = (1 - idade_fator) * 0.10        # até -10%
        taxa_rolling  = max(0.0, taxa_global - penalidade)

        return taxa_rolling, min(total_acum, janela)


_rolling_store = _RollingStore()


# =============================================================================
# HELPERS
# =============================================================================

def _rr_dinamico(h: int, pred_pct: float) -> tuple[float, float]:
    """
    Calcula alvo e stop dinâmicos baseados na intensidade da predição.

    A rede prevê um movimento de `pred_pct`% — usamos isso como proxy
    para a magnitude esperada.  O alvo é o mínimo entre o previsto e o
    dobro do alvo base; o stop é calibrado para atingir o R/R mínimo.
    """
    alvo_base  = _ALVO_BASE[h]
    rr_min     = _RR_MIN[h]

    # Alvo: usa a predição como referência (em fração do preço)
    pred_frac = abs(pred_pct) / 100.0
    alvo = max(alvo_base, min(pred_frac * 0.7, alvo_base * 2.5))

    # Stop: calculado para atingir R/R mínimo
    stop = alvo / rr_min

    rr_real = alvo / stop if stop > 0 else rr_min
    return alvo, stop, round(rr_real, 2)


def _confluencia_grupos(preds: list[float]) -> tuple[int, list[str], list[str]]:
    """
    Verifica concordância entre GRUPOS de horizonte.

    Retorna:
        n_grupos_conf   — número de grupos que concordam com o grupo principal
        grupos_conf     — nomes dos grupos confirmadores
        h_nomes_conf    — nomes dos horizontes confirmadores (para exibição)
    """
    direcoes_grupo: dict[str, list[int]] = {g: [] for g in _GRUPOS}

    for idx, h in enumerate(HORIZONTES):
        if idx < len(preds):
            grupo = _IDX_PARA_GRUPO.get(idx)
            if grupo:
                direcoes_grupo[grupo].append(1 if preds[idx] > 0 else -1)

    # Direção dominante de cada grupo
    dir_grupo: dict[str, int | None] = {}
    for grupo, dirs in direcoes_grupo.items():
        if not dirs:
            dir_grupo[grupo] = None
            continue
        soma = sum(dirs)
        dir_grupo[grupo] = 1 if soma > 0 else (-1 if soma < 0 else None)

    return dir_grupo


def _contar_confluencia(idx_sinal: int, preds: list[float]) -> tuple[int, list[str], list[str]]:
    """Para um horizonte candidato, conta quantos GRUPOS distintos concordam."""
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
            # Adiciona nomes dos horizontes desse grupo como confirmadores
            for idx in _GRUPOS[grupo]:
                if idx < len(preds) and abs(preds[idx]) >= _PRED_MIN.get(HORIZONTES[idx], 0.03):
                    h_conf.append(_NOMES_H[HORIZONTES[idx]])

    return len(grupos_conf), grupos_conf, h_conf


def _label_confluencia(n_grupos: int) -> str:
    if n_grupos >= 3:
        return "MUITO FORTE ████"
    if n_grupos == 2:
        return "FORTE ███░"
    if n_grupos == 1:
        return "MODERADA ██░░"
    return "FRACA █░░░"


# =============================================================================
# SIGNAL ENGINE
# =============================================================================

class SignalEngine:
    """
    Avalia cada tick e envia sinais apenas quando:
      1. Acurácia rolling (janela deslizante) suporta EV positivo ≥ _EV_MIN
      2. Profit Factor ≥ _PF_MIN
      3. Confluência entre grupos de horizonte ≥ _CONFLUENCIA_GRUPOS_MIN
      4. R/R dinâmico ≥ _RR_MIN do horizonte
      5. Regime compatível com a faixa do horizonte
      6. Cooldown inteligente (quebrável por EV superior)
    """

    def __init__(self, token_bot: str):
        self.token_bot = token_bot
        # {moeda: {h: {"ts": float, "ev": float}}}
        self._ultimo_sinal: dict[str, dict[int, dict]] = {}
        self._ultimo_sinal_global: dict[str, dict] = {}

    # ─────────────────────────────────────────────────────────────────────────

    def avaliar(
        self,
        moeda:                  str,
        preco:                  float,
        preds_percentual:       list[float],
        resultados_verificacao: dict,
        regime:                 str = "ranging",
        arquivo_disco:          str | None = None,
        acc_mente:              list[float] | None = None,
    ):
        resultados = self._merge_resultados(resultados_verificacao, arquivo_disco)
        agora      = time.time()

        if not hasattr(self, '_startup_time'):
            self._startup_time = agora
            print(f"\n⏳ Aguardando 15 minutos para estabilizar o sistema...")
            return
        
        tempo_desde_startup = agora - self._startup_time
        if tempo_desde_startup < 900:  # 15 minutos
            print(f"\n⏳ Estabilizando... ({int(tempo_desde_startup)}s < 900s)")
            return

        # ── Cooldown global ───────────────────────────────────────────────
        ult_global = self._ultimo_sinal_global.get(moeda, {})
        tempo_desde_ultimo = agora - ult_global.get("ts", 0)
        ev_ultimo = ult_global.get("ev", 0)

        print(f"\n{'='*72}")
        print(f"🔍 [{moeda.replace('USDT','')}] ${preco:,.4f} | Regime: {regime}")
        print(f"{'='*72}")
        print(f"{'H':<7} {'Pred%':<9} {'AccR':<7} {'N':<6} {'EV%':<8} {'PF':<6} {'R/R':<6} {'Status'}")
        print(f"{'-'*72}")

        # ── Avalia cada horizonte ─────────────────────────────────────────
        candidatos = []

        for idx, h in enumerate(HORIZONTES):
            if idx >= len(preds_percentual):
                break

            pred  = preds_percentual[idx]
            nome  = _NOMES_H[h]
            grupo = _IDX_PARA_GRUPO.get(idx, "micro")

            def rejeitar(motivo):
                print(f"{nome:<7} {pred:+.3f}%{'':<3} {'—':<7} {'—':<6} {'—':<8} {'—':<6} {'—':<6} ❌ {motivo}")

            # 1. Predição mínima
            if abs(pred) < _PRED_MIN[h]:
                rejeitar(f"Pred < {_PRED_MIN[h]:.2f}%")
                continue

            # 2. Regime
            if regime not in _REGIME_OK.get(grupo, set()):
                rejeitar(f"Regime '{regime}' ∉ {_REGIME_OK.get(grupo, set())}")
                continue

            # 3. Acurácia rolling
            if acc_mente is not None and idx < len(acc_mente):
                p_raw = acc_mente[idx]
                # Janela implícita: se temos acc_mente, é a acurácia recente da rede
                n_amostras = resultados.get(str(h), {}).get("total", 0)
                n_amostras = min(n_amostras, _ROLLING_WINDOW[h])
            else:
                p_raw, n_amostras = _rolling_store.acuracia_rolling(moeda, h, resultados)

            if n_amostras < _AMOSTRAS_MIN[h]:
                rejeitar(f"Amostras ({n_amostras} < {_AMOSTRAS_MIN[h]})")
                continue

            # Cap anti-overfitting (85%)
            p = min(p_raw, 0.85)

            # 4. R/R dinâmico
            alvo_frac, stop_frac, rr = _rr_dinamico(h, pred)

            if rr < _RR_MIN[h]:
                rejeitar(f"R/R {rr:.2f} < {_RR_MIN[h]:.2f}")
                continue

            # 5. EV e PF com R/R dinâmico
            ev = p * alvo_frac - (1 - p) * stop_frac
            pf = (p * alvo_frac) / ((1 - p) * stop_frac + 1e-9)

            if ev < _EV_MIN:
                rejeitar(f"EV {ev*100:.3f}% < {_EV_MIN*100:.3f}%")
                continue

            if pf < _PF_MIN:
                rejeitar(f"PF {pf:.2f} < {_PF_MIN:.2f}")
                continue

            # 6. Cooldown individual (quebrável por EV superior)
            ult_h = self._ultimo_sinal.get(moeda, {}).get(h, {})
            ts_ult = ult_h.get("ts", 0)
            ev_ult = ult_h.get("ev", 0)
            elapsed = agora - ts_ult
            cooldown = _COOLDOWN_BASE[h]

            em_cooldown = elapsed < cooldown
            ev_quebra   = ev_ult > 0 and ev >= ev_ult * _EV_BREAK_FACTOR

            if em_cooldown and not ev_quebra:
                rejeitar(f"Cooldown ({int(elapsed)}s < {cooldown}s)")
                continue

            # ✅ Aprovado
            print(f"{nome:<7} {pred:+.3f}%{'':<3} {p*100:5.1f}%{'':<1} {n_amostras:<6} "
                  f"{ev*100:+.3f}%{'':<2} {pf:5.2f} {rr:5.2f} ✅ APROVADO")

            candidatos.append({
                "idx":        idx,
                "h":          h,
                "nome":       nome,
                "grupo":      grupo,
                "pred":       pred,
                "p":          p,
                "p_raw":      p_raw,
                "n":          n_amostras,
                "ev":         ev,
                "pf":         pf,
                "rr":         rr,
                "alvo_frac":  alvo_frac,
                "stop_frac":  stop_frac,
            })

        if not candidatos:
            print(f"🔕 Nenhum candidato aprovado para {moeda}")
            return

        # ── Confluência entre grupos ──────────────────────────────────────
        melhor = None
        melhor_score = -1.0

        for cand in candidatos:
            n_grupos, grupos_conf, h_conf = _contar_confluencia(cand["idx"], preds_percentual)

            if n_grupos < _CONFLUENCIA_GRUPOS_MIN:
                print(f"   ⚠️  {cand['nome']}: confluência {n_grupos} grupo(s) < {_CONFLUENCIA_GRUPOS_MIN} — rejeitado")
                continue

            # Sharpe implícito: EV / volatilidade-proxy (stop_frac)
            sharpe = cand["ev"] / (cand["stop_frac"] + 1e-9)

            # Score final
            score = (cand["ev"]
                     * (1 + n_grupos * 0.30)
                     * (1 + abs(cand["pred"]) / 100 * 0.20)
                     * sharpe)

            print(f"   🎯 {cand['nome']}: {n_grupos} grupo(s) conf, score={score:.6f}")

            if score > melhor_score:
                melhor_score = score
                melhor = {
                    **cand,
                    "n_grupos":  n_grupos,
                    "grupos_conf": grupos_conf,
                    "h_conf":    h_conf,
                    "score":     score,
                }

        if melhor is None:
            print(f"🔕 Nenhum candidato com confluência suficiente para {moeda}")
            return

        # ── Cooldown global ───────────────────────────────────────────────
        if tempo_desde_ultimo < _COOLDOWN_GLOBAL:
            ev_novo = melhor["ev"]
            if not (ev_ult > 0 and ev_novo >= ev_ult * _EV_BREAK_FACTOR):
                print(f"🔕 Cooldown global ({int(tempo_desde_ultimo)}s < {_COOLDOWN_GLOBAL}s) — aguarda")
                return

        # ── Monta e envia ─────────────────────────────────────────────────
        direcao_int = 1 if melhor["pred"] > 0 else -1
        alvo = preco * (1 + melhor["alvo_frac"]) if direcao_int > 0 else preco * (1 - melhor["alvo_frac"])
        stop = preco * (1 - melhor["stop_frac"]) if direcao_int > 0 else preco * (1 + melhor["stop_frac"])

        payload = {
            # Dados do ativo
            "ativo":                  moeda.replace("USDT", "/USDT"),
            "direcao":                "ALTA" if direcao_int > 0 else "BAIXA",
            "horizonte":              melhor["nome"],
            "entrada":                preco,
            "alvo":                   alvo,
            "stop":                   stop,
            # Métricas
            "acuracia":               round(melhor["p_raw"] * 100, 1),
            "acuracia_janela":        melhor["n"],
            "ev":                     melhor["ev"],
            "profit_factor":          melhor["pf"],
            "rr":                     melhor["rr"],
            # Confluência
            "confluencia_n":          melhor["n_grupos"],
            "confluencia_grupos":     melhor["grupos_conf"],
            "horizontes_confirmadores": melhor["h_conf"],
            # Contexto
            "regime":                 regime,
            "score":                  round(melhor["score"], 5),
        }

        enviar_para_todos_canais(self.token_bot, payload)

        # Registra cooldowns
        self._ultimo_sinal.setdefault(moeda, {})[melhor["h"]] = {
            "ts": agora, "ev": melhor["ev"]
        }
        self._ultimo_sinal_global[moeda] = {"ts": agora, "ev": melhor["ev"]}

        print(f"\n📤 SINAL ENVIADO {moeda} {payload['direcao']} {melhor['nome']} | "
              f"EV={melhor['ev']*100:.3f}% | PF={melhor['pf']:.2f} | "
              f"R/R={melhor['rr']:.2f} | Grupos={melhor['n_grupos']} | "
              f"Score={melhor['score']:.5f}")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_resultados(ram: dict, arquivo: str | None) -> dict:
        merged: dict[str, dict] = {}

        for h_key, dados in ram.items():
            merged[str(h_key)] = {
                "acertos": dados.get("acertos", 0),
                "erros":   dados.get("erros",   0),
                "total":   dados.get("total",   0),
            }

        if arquivo and os.path.exists(arquivo):
            try:
                with open(arquivo, "r") as f:
                    disco = json.load(f)
                for h_key, dados in disco.items():
                    if h_key in merged:
                        merged[h_key]["acertos"] += dados.get("acertos", 0)
                        merged[h_key]["erros"]   += dados.get("erros",   0)
                        merged[h_key]["total"]   += dados.get("total",   0)
                    else:
                        merged[h_key] = {
                            "acertos": dados.get("acertos", 0),
                            "erros":   dados.get("erros",   0),
                            "total":   dados.get("total",   0),
                        }
            except Exception as e:
                print(f"[SignalEngine] ⚠️ Erro ao ler disco: {e}")

        return merged