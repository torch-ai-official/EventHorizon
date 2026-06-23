# signal_engine.py
# Cole este arquivo em Software/core/ e importe no crypto.py
#
# Substitui verificar_e_enviar_sinal() por uma versão quantitativa:
#
#   from Software.core.signal_engine import SignalEngine
#   self._signal_engine = SignalEngine(TELEGRAM_TOKEN)          # no __init__
#   self._signal_engine.avaliar(moeda, preco, preds_percentual, # no update()
#                               resultados_verificacao, regime)
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import math
import time
from collections import deque
from telegram_sender import enviar_para_todos_canais

# Horizontes exportados pelo mind_pytorch.py
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

# Alvo e stop dinâmicos por horizonte (fração do preço)
_ALVO_H = {
    5:     0.0015,
    15:    0.0020,
    30:    0.0025,
    60:    0.0030,
    300:   0.0060,
    900:   0.0100,
    1800:  0.0140,
    3600:  0.0200,
    18000: 0.0350,
    86400: 0.0600,
}
_STOP_H = {k: v * 0.5 for k, v in _ALVO_H.items()}   # stop = metade do alvo → R/R base 1:2


# ─────────────────────────────────────────────────────────────────────────────
# FILTROS QUANTITATIVOS
# ─────────────────────────────────────────────────────────────────────────────

# Amostras mínimas por horizonte (mais tempo → acumula mais devagar)
_AMOSTRAS_MIN = {
    5:     200,
    15:    150,
    30:    120,
    60:    100,
    300:   80,
    900:   60,
    1800:  50,
    3600:  40,
    18000: 20,
    86400: 10,
}

# EV mínimo esperado por operação (como fração do preço)
# EV = p * ganho - (1-p) * perda   onde ganho/perda = _ALVO_H / _STOP_H
_EV_MIN = 0.0025          # 0.25% de expectativa mínima por trade

# Profit Factor mínimo
_PF_MIN = 1.20

# Confluência mínima: quantos horizontes vizinhos precisam concordar
_CONFLUENCIA_MIN = 2

# Cooldown por ativo em segundos (evita spam)
_COOLDOWN = {
    5:     120,
    15:    180,
    30:    240,
    60:    300,
    300:   600,
    900:   900,
    1800:  1800,
    3600:  3600,
    18000: 7200,
    86400: 43200,
}

# Regimes compatíveis com cada tipo de horizonte
_REGIME_OK = {
    "curto":    {"trend_up", "trend_down", "volatile"},
    "medio":    {"trend_up", "trend_down", "ranging"},
    "longo":    {"trend_up", "trend_down", "ranging"},
}

def _tipo_horizonte(h: int) -> str:
    if h <= 60:
        return "curto"
    if h <= 1800:
        return "medio"
    return "longo"


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SignalEngine:
    """
    Avalia cada tick e dispara sinais apenas quando há:
      1. Expected Value positivo e acima de _EV_MIN
      2. Profit Factor ≥ _PF_MIN
      3. Confluência multi-horizonte ≥ _CONFLUENCIA_MIN
      4. Regime de mercado compatível com o prazo
      5. Cooldown respeitado por ativo/horizonte
    """

    def __init__(self, token_bot: str):
        self.token_bot = token_bot
        # _ultimo_sinal[moeda][horizonte] = timestamp
        self._ultimo_sinal: dict[str, dict[int, float]] = {}
        self._ultimo_sinal_global: dict[str, float] = {}  # Cooldown por moeda

    # ─────────────────────────────────────────────────────────────────────────
    # PONTO DE ENTRADA PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def avaliar(
        self,
        moeda: str,
        preco: float,
        preds_percentual: list[float],
        resultados_verificacao: dict,
        regime: str = "ranging",
        arquivo_disco: str | None = None,
    ):
        resultados = self._merge_resultados(resultados_verificacao, arquivo_disco)
        agora = time.time()
        ultimo_global = self._ultimo_sinal_global.get(moeda, 0)
        if agora - ultimo_global < 300:
            print(f"\n🔕 [{moeda}] Cooldown global ({int(agora - ultimo_global)}s) — aguardando {300 - int(agora - ultimo_global)}s")
            return
        # ⭐ CABEÇALHO DO DEBUG
        print(f"\n{'='*70}")
        print(f"🔍 [DEBUG] {moeda.replace('USDT', '')} | Preço: ${preco:,.2f} | Regime: {regime}")
        print(f"{'='*70}")
        print(f"{'Horizonte':<8} {'Pred':<10} {'Trades':<8} {'Acur':<8} {'EV':<10} {'PF':<8} {'Regime':<10} {'Status'}")
        print(f"{'-'*70}")

        # ── 1. Calcula métricas por horizonte ─────────────────────────────
        candidatos = []
        for idx, h in enumerate(HORIZONTES):
            if idx >= len(preds_percentual):
                continue

            pred = preds_percentual[idx]
            nome_h = _NOMES_H[h]

            # Check 1: Previsão
            if abs(pred) < 0.05:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {'—':<8} {'—':<8} {'—':<10} {'—':<8} {'—':<10} ❌ Previsão < 0.05%")
                continue

            h_str = str(h)
            dados_h = resultados.get(h_str, {})
            total = dados_h.get("total", 0)
            acertos = dados_h.get("acertos", 0)

            # Check 2: Amostras
            if total < _AMOSTRAS_MIN[h]:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {'—':<8} {'—':<10} {'—':<8} {'—':<10} ❌ Amostras ({total} < {_AMOSTRAS_MIN[h]})")
                continue

            p = acertos / total
            ganho = _ALVO_H[h]
            perda = _STOP_H[h]
            ev = p * ganho - (1 - p) * perda
            pf = (p * ganho) / ((1 - p) * perda + 1e-9)

            # Check 3: EV
            if ev < _EV_MIN:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {p*100:5.1f}%{'':<2} {ev*100:.3f}%{'':<5} {pf:.2f}{'':<4} {'—':<10} ❌ EV ({ev*100:.3f}% < {_EV_MIN*100:.3f}%)")
                continue

            # Check 4: PF
            if pf < _PF_MIN:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {p*100:5.1f}%{'':<2} {ev*100:.3f}%{'':<5} {pf:.2f}{'':<4} {'—':<10} ❌ PF ({pf:.2f} < {_PF_MIN})")
                continue

            # Check 5: Regime
            tipo = _tipo_horizonte(h)
            if regime not in _REGIME_OK[tipo]:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {p*100:5.1f}%{'':<2} {ev*100:.3f}%{'':<5} {pf:.2f}{'':<4} {regime:<10} ❌ Regime incompatível")
                continue

            # Check 6: Cooldown
            ultimo = self._ultimo_sinal.get(moeda, {}).get(h, 0)
            if agora - ultimo < _COOLDOWN[h]:
                print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {p*100:5.1f}%{'':<2} {ev*100:.3f}%{'':<5} {pf:.2f}{'':<4} {regime:<10} ❌ Cooldown")
                continue

            # ✅ PASSOU EM TUDO!
            print(f"{nome_h:<8} {pred:+.4f}%{'':<4} {total:<8} {p*100:5.1f}%{'':<2} {ev*100:.3f}%{'':<5} {pf:.2f}{'':<4} {regime:<10} ✅✅✅ APROVADO!")
            candidatos.append({
                "idx": idx, "h": h, "nome": nome_h, "pred": pred,
                "acuracia": round(p * 100, 1), "ev": ev,
                "pf": round(pf, 2), "total": total
            })

        if not candidatos:
            print(f"\n🔕 NENHUM candidato passou nos filtros para {moeda}")
            return

        # ── 2. Confluência ─────────────────────────────────────────────────
        direcao_por_idx = {}
        for idx, h in enumerate(HORIZONTES):
            if idx < len(preds_percentual):
                direcao_por_idx[idx] = 1 if preds_percentual[idx] > 0 else -1

        melhor_sinal = None
        melhor_score = -1.0

        for cand in candidatos:
            idx = cand["idx"]
            direcao = 1 if cand["pred"] > 0 else -1

            # Conta horizontes vizinhos que concordam
            n_conf = 0
            conf_nomes = []
            for j in range(max(0, idx - 3), min(len(HORIZONTES), idx + 4)):
                if j == idx:
                    continue
                if direcao_por_idx.get(j) == direcao:
                    n_conf += 1
                    conf_nomes.append(_NOMES_H[HORIZONTES[j]])

            if n_conf < _CONFLUENCIA_MIN:
                continue

            # Score final
            score = cand["ev"] * (1 + n_conf * 0.25) * (1 + abs(cand["pred"]) * 0.1)

            if score > melhor_score:
                melhor_score = score
                melhor_sinal = {**cand, "n_conf": n_conf, "conf_nomes": conf_nomes,
                                "direcao": direcao, "regime": regime}
                

        if melhor_sinal is None:
            return
        
        


        # ── 3. Monta e envia ───────────────────────────────────────────────
        h = melhor_sinal["h"]
        direcao = melhor_sinal["direcao"]
        ganho_h = _ALVO_H[h]
        perda_h = _STOP_H[h]

        alvo = preco * (1 + ganho_h) if direcao > 0 else preco * (1 - ganho_h)
        stop = preco * (1 - perda_h) if direcao > 0 else preco * (1 + perda_h)

        payload = {
            "ativo": moeda.replace("USDT", "/USDT"),
            "direcao": "ALTA" if direcao > 0 else "BAIXA",
            "horizonte": melhor_sinal["nome"],
            "entrada": preco,
            "alvo": alvo,
            "stop": stop,
            "acuracia": melhor_sinal["acuracia"],
            "profit_factor": melhor_sinal["pf"],
        }

        enviar_para_todos_canais(self.token_bot, payload)
        self._ultimo_sinal.setdefault(moeda, {})[h] = agora
        self._ultimo_sinal_global[moeda] = agora

        print(f"\n[SINAL] 📤 {moeda} {payload['direcao']} {payload['horizonte']} | "
            f"EV={melhor_sinal['ev']*100:.2f}% | PF={melhor_sinal['pf']:.2f} | "
            f"Conf={melhor_sinal['n_conf']} | Score={melhor_score:.4f}")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_resultados(ram: dict, arquivo: str | None) -> dict:
        """Combina resultados em RAM com os persistidos em disco."""
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