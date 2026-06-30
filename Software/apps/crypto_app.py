#crypto.py
import json
from datetime import datetime
import math
import os
import torch
import requests
import random

import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from Software.core.universe_instance import lock_universo
from Software.core.mind_pytorch import MenteTorch, HORIZONTES, N_HORIZONTES
from Software.core.mind_pytorch import DelayedRewardBuffer
from telegram_sender import enviar_sinal_telegram, formatar_sinal_pt, enviar_para_todos_canais
from Software.core.sinal_engine import SignalEngine

# Configurações do Bot
TELEGRAM_TOKEN = "8898574077:AAFnKzYpum6CWiZgca4zgvAo6hB79qnT-rM"
CANAL_VIP_ID = "-1004322239279"

def pegar_todos_precos(tentativas=2):
    url = "https://api.binance.com/api/v3/ticker/price"
    for _ in range(tentativas):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return {item["symbol"]: float(item["price"]) for item in data}
        except Exception as e:
            print(f"[CryptoApp] Tentativa falhou: {e}")
            time.sleep(1)
    return {}

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

# =============================================================================
#  INDICADORES TÉCNICOS
# =============================================================================

def calcular_ema(precos, periodo):
    if len(precos) < periodo:
        return precos[-1] if precos else 0
    k = 2 / (periodo + 1)
    ema = precos[0]
    for p in precos:
        ema = p * k + ema * (1 - k)
    return ema


def calcular_rsi(precos, periodo=14):
    if len(precos) < periodo + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(precos)):
        diff = precos[i] - precos[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-periodo:]) / periodo
    avg_loss = sum(losses[-periodo:]) / periodo
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calcular_bollinger(precos, periodo=20, mult=2.0):
    if len(precos) < periodo:
        return precos[-1], precos[-1], precos[-1]
    janela = precos[-periodo:]
    media = sum(janela) / periodo
    variancia = sum((p - media) ** 2 for p in janela) / periodo
    desvio = math.sqrt(variancia)
    return media + mult * desvio, media, media - mult * desvio


def calcular_atr(candles, periodo=14):
    if len(candles) < 2:
        return 0
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    janela = trs[-periodo:]
    return sum(janela) / len(janela)


def calcular_macd(precos):
    if len(precos) < 26:
        return 0, 0, 0
    ema12 = calcular_ema(precos, 12)
    ema26 = calcular_ema(precos, 26)
    macd = ema12 - ema26
    return macd, 0, macd


def detectar_regime(precos, candles):
    if len(precos) < 20:
        return "ranging"
    ema9  = calcular_ema(precos, 9)
    ema21 = calcular_ema(precos, 21)
    atr   = calcular_atr(candles) if len(candles) >= 2 else 0
    bb_upper, bb_mid, bb_lower = calcular_bollinger(precos)
    bb_width = (bb_upper - bb_lower) / (bb_mid + 1e-9)
    preco_atual = precos[-1]
    retorno_20 = (preco_atual - precos[-20]) / precos[-20]
    if bb_width > 0.02:
        return "volatile"
    elif ema9 > ema21 and retorno_20 > 0.001:
        return "trend_up"
    elif ema9 < ema21 and retorno_20 < -0.001:
        return "trend_down"
    else:
        return "ranging"


def detectar_padroes_candle(candles):
    if len(candles) < 3:
        return 0
    score = 0
    c0 = candles[-1]
    c1 = candles[-2]
    c2 = candles[-3]
    corpo0 = abs(c0["close"] - c0["open"])
    amplitude0 = c0["high"] - c0["low"] + 1e-9
    sombra_baixa = c0["open"] - c0["low"] if c0["close"] >= c0["open"] else c0["close"] - c0["low"]
    sombra_alta  = c0["high"] - c0["close"] if c0["close"] >= c0["open"] else c0["high"] - c0["open"]
    if sombra_baixa > corpo0 * 2 and sombra_alta < corpo0 * 0.5:
        score += 1.5
    if sombra_alta > corpo0 * 2 and sombra_baixa < corpo0 * 0.5:
        score -= 1.5
    if (c1["close"] < c1["open"] and c0["close"] > c0["open"] and
            c0["open"] < c1["close"] and c0["close"] > c1["open"]):
        score += 2.0
    if (c1["close"] > c1["open"] and c0["close"] < c0["open"] and
            c0["open"] > c1["close"] and c0["close"] < c1["open"]):
        score -= 2.0
    if (c2["close"] > c2["open"] and c1["close"] > c1["open"] and
            c0["close"] > c0["open"] and c1["close"] > c2["close"] and
            c0["close"] > c1["close"]):
        score += 1.5
    if (c2["close"] < c2["open"] and c1["close"] < c1["open"] and
            c0["close"] < c0["open"] and c1["close"] < c2["close"] and
            c0["close"] < c1["close"]):
        score -= 1.5
    return score


# =============================================================================
#  PESOS ADAPTATIVOS (MANTIDO IGUAL)
# =============================================================================

class PesosAdaptativos:

    def __init__(self, n_features=12):
        self.n_features = n_features
        self.pesos  = [random.uniform(-0.1, 0.1) for _ in range(n_features)]
        self.bias   = 0.0
        self.lr     = 0.01
        self.decay  = 0.98
        self.bias_decay = 0.995
        self.n_acertos = 0
        self.n_erros   = 0
        self.historico_loss = deque(maxlen=50)
        self.media_retorno  = 0.0
        self.alpha_media    = 0.3
        self.historico_sinais = deque(maxlen=10)

    def debias_target(self, target: float) -> float:
        self.media_retorno = (
            self.alpha_media * target +
            (1 - self.alpha_media) * self.media_retorno
        )
        return target - self.media_retorno

    @property
    def vies_direcional(self) -> float:
        if not self.historico_sinais:
            return 0.5
        return sum(1 for s in self.historico_sinais if s > 0) / len(self.historico_sinais)

    def forward(self, features: list) -> float:
        raw = sum(p * f for p, f in zip(self.pesos, features)) + self.bias
        vies = self.vies_direcional
        if vies > 0.6:
            correcao = -(vies - 0.5) * abs(raw) * 0.6
            raw += correcao
        elif vies < 0.4:
            correcao = (0.5 - vies) * abs(raw) * 0.6
            raw += correcao
        return raw

    def update(self, features: list, target: float) -> float:
        pred = self.forward(features)
        self.historico_sinais.append(pred)
        target_db = self.debias_target(target)
        erro = target_db - pred
        self.historico_loss.append(abs(erro))
        for i in range(min(self.n_features, len(features))):
            self.pesos[i] = self.pesos[i] * self.decay + self.lr * erro * features[i]
        self.bias = self.bias * self.bias_decay + self.lr * erro * 0.05
        return pred

    @property
    def accuracy(self) -> float:
        total = self.n_acertos + self.n_erros
        return self.n_acertos / total if total > 0 else 0.5

    @property
    def loss_medio(self) -> float:
        return sum(self.historico_loss) / len(self.historico_loss) if self.historico_loss else 1.0


# =============================================================================
#  CRYPTO APP - VERSÃO QUE FUNCIONA (BASEADA NO CÓDIGO ANTIGO)
# =============================================================================

class CryptoApp:

    nome = "crypto_app"

    def __init__(self, universo):
        
        self._signal_engine = SignalEngine(TELEGRAM_TOKEN)
        
        self.universo      = universo
        self.ultimo_update = 0
        self.delay         = 2.0
        self.ativo         = False
        self.ids_cripto    = {}
        self.precos        = {}
        self.rodando_api   = False
        self.timeframe     = 5
        self.loop_thread   = None
        self.buffers: dict[str, DelayedRewardBuffer] = {}
        self._tick_contador: dict[str, dict[int, int]] = {}  # {moeda: {h: contador}}
        self.verificacoes: dict[str, deque] = {}
        self.resultados_verificacao: dict[str, dict] = {}
        self.historico_individual: dict[str, dict] = {}

        self.pesos: dict[str, PesosAdaptativos] = {}
        self.features_anteriores: dict[str, list] = {}
        self.preco_anterior: dict[str, float] = {}

        # Lock separado para mentes_pytorch
        self.mentes_pytorch: dict[str, MenteTorch] = {}
        self._lock_mentes = threading.Lock()

        # Executor para inicialização assíncrona
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mente_init")

        self.lista_moedas = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
            "SOLUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"
        ]

        self.carregar_ultimas_moedas()

    # ─────────────────────────────────────────────────────────────────────────
    # INICIALIZAÇÃO ASSÍNCRONA DE MENTES
    # ─────────────────────────────────────────────────────────────────────────

    def _init_mente_async(self, moeda: str, id_agente: int):
        try:
            mente = MenteTorch(id_agente=id_agente)
            
            # Tenta carregar do arquivo com nome da MOEDA
            arquivo_moeda = f"data/mentes_pytorch/mente_{moeda}.pt"
            if os.path.exists(arquivo_moeda):
                try:
                    ck = torch.load(arquivo_moeda, map_location='cpu')
                    mente.load_state_dict(ck['model_state_dict'], strict=False)
                    mente.n_acertos = ck.get('n_acertos', [0]*10)
                    mente.n_erros = ck.get('n_erros', [0]*10)
                    mente.geracao = ck.get('geracao', 0)
                    print(f"[CRYPTO] ♻️ Mente {moeda} RECARREGADA do disco ({mente.geracao} gerações)")
                except Exception as e:
                    print(f"[CRYPTO] ⚠️ Erro ao carregar {moeda}: {e}")
            
            with self._lock_mentes:
                self.mentes_pytorch[moeda] = mente
            
            print(f"[CRYPTO] ✅ Mente {moeda} (ID {id_agente}) pronta")
        except Exception as e:
            print(f"[CRYPTO] ❌ Erro: {e}")

    def _garantir_mente(self, moeda: str) -> MenteTorch | None:
        with self._lock_mentes:
            return self.mentes_pytorch.get(moeda)
        
    def _deve_registrar_verificacao(self, moeda: str, h: int) -> bool:
        """Subsampling: só registra 1 a cada N ticks por horizonte."""
        if moeda not in self._tick_contador:
            self._tick_contador[moeda] = {}
        if h not in self._tick_contador[moeda]:
            self._tick_contador[moeda][h] = 0
        
        self._tick_contador[moeda][h] += 1
        fator = _FATOR_SUBSAMPLE.get(h, 1)
        
        return self._tick_contador[moeda][h] % fator == 0

    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE
    # ─────────────────────────────────────────────────────────────────────────

    def handle(self, comando):

        if comando == "crypto start":
            if self.ativo:
                return ["Crypto app já está rodando"]
            self.ativo = True
            self.rodando_api = True
            if self.loop_thread is None or not self.loop_thread.is_alive():
                self.loop_thread = threading.Thread(target=self.loop_api, daemon=True)
                self.loop_thread.start()
            return ["Crypto app started"]

        if comando == "crypto spawn all":
            return self.spawn_moedas(self.lista_moedas)

        if comando.startswith("crypto spawn"):
            partes = comando.split()
            moedas = [m.upper() for m in partes[2:]]
            self.salvar_ultimas_moedas()
            resultado = self.spawn_moedas(moedas)
            
            if self.rodando_api:
                self.rodando_api = False
                time.sleep(1)
                self.rodando_api = True
                self.loop_thread = threading.Thread(target=self.loop_api, daemon=True)
                self.loop_thread.start()
                resultado.append("🔄 IA reiniciada com novas moedas")
            
            return resultado

        if comando == "crypto signal":
            return self._gerar_sinais()

        if comando == "crypto stop":
            self.ativo = False
            self.rodando_api = False
            self.universo.mentes.salvar(salvar_modelos=True)
            return ["Crypto app stopped and cleaned"]

        if comando == "crypto clear":
            self.remover_moedas()
            self.universo.mentes.salvar(salvar_modelos=True)
            return ["All coins removed"]

        if comando.startswith("crypto timeframe"):
            try:
                tf = int(comando.split()[2])
                self.timeframe = tf
                return [f"Timeframe set to {tf}s"]
            except:
                return ["Invalid timeframe"]

        if comando == "crypto stats":
            return self._gerar_stats()

        if comando == "refresh":
            return ["refreshed"]

        if comando == "crypto report":
            relatorio = self.gerar_relatorio_desempenho()
            return [json.dumps(relatorio)]
        
        if comando == "crypto rr":
            self.medir_risk_reward()
            return ["📊 Análise de Risk/Reward gerada no terminal"]

        if comando.startswith("crypto remove"):
            partes = comando.split()
            moedas = [m.upper() for m in partes[2:]]
            removidas = self.remover_moedas_selecionadas(moedas)
            self.salvar_ultimas_moedas()
            return [f"Removidas: {', '.join(removidas)}" if removidas else "Nenhuma moeda removida"]

        if comando.startswith("crypto "):
            return ["Unknown crypto command"]

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # UPDATE PRINCIPAL - VERSÃO QUE FUNCIONA (IGUAL AO ANTIGO)
    # ─────────────────────────────────────────────────────────────────────────

    def update(self):
        if not self.ativo:
            return

        agora = time.time()
        if agora - self.ultimo_update < self.delay:
            return
        self.ultimo_update = agora

        dados_ativos = {}
        for moeda, id_dado in self.ids_cripto.items():
            dado = next((d for d in self.universo.dados if d["id"] == id_dado), None)
            if dado is not None:
                dados_ativos[moeda] = dado

        clusters_universo = self.universo.detectar_clusters()
        cluster_por_id = {}
        for cluster in clusters_universo:
            for d in cluster:
                cluster_por_id[d["id"]] = cluster

        for moeda, dado in dados_ativos.items():
            preco = self.precos.get(moeda)
            if preco is None:
                continue

            dado["history"].append({"time": int(time.time()), "price": preco})
            if len(dado["history"]) > 200:
                dado["history"].pop(0)

            precos = [p["price"] for p in dado["history"]]

            if not isinstance(precos, list):
                precos = []

            if len(precos) < 26:
                dado["price"] = preco
                continue

            # ── Candles ───────────────────────────────────────────────────────
            if "candles" not in dado:
                dado["candles"] = []

            atual_time = int(time.time())
            candle_time = atual_time - (atual_time % self.timeframe)

            if len(dado["candles"]) == 0 or dado["candles"][-1]["time"] != candle_time:
                dado["candles"].append({
                    "time":  candle_time,
                    "open":  preco,
                    "high":  preco,
                    "low":   preco,
                    "close": preco
                })
            else:
                c = dado["candles"][-1]
                c["high"] = max(c["high"], preco)
                c["low"]  = min(c["low"],  preco)
                c["close"] = preco

            if len(dado["candles"]) > 200:
                dado["candles"].pop(0)

            candles = dado["candles"]

            # ── Indicadores técnicos ──────────────────────────────────────────
            ema9        = calcular_ema(precos, 9)
            ema21       = calcular_ema(precos, 21)
            ema50       = calcular_ema(precos, 50) if len(precos) >= 50 else ema21
            rsi         = calcular_rsi(precos)
            macd, _, _  = calcular_macd(precos)
            atr         = calcular_atr(candles)
            bb_upper, bb_mid, bb_lower = calcular_bollinger(precos)

            retorno    = (preco - precos[-2]) / precos[-2]
            retorno_5  = (preco - precos[-5]) / precos[-5]
            retorno_10 = (preco - precos[-10]) / precos[-10] if len(precos) >= 10 else 0

            regime       = detectar_regime(precos, candles)
            padrao_score = detectar_padroes_candle(candles)

            bb_pos      = (preco - bb_mid) / (bb_upper - bb_lower + 1e-9)
            vol_recente = atr / (preco + 1e-9)

            memoria_score = self.universo.score_memoria(dado)

            sync_score    = 0.0
            minha_cluster = cluster_por_id.get(dado["id"], [])
            for outro_dado in minha_cluster:
                if outro_dado["id"] == dado["id"]:
                    continue
                sync        = self.universo.sincronizacao(dado, outro_dado)
                sinal_outro = outro_dado.get("previsao", 0)
                sync_score += sync * sinal_outro * 0.3

            agora_dt = datetime.now()
            hora = agora_dt.hour
            minuto = agora_dt.minute
            segundo = agora_dt.second
            tempo_segundos = (hora * 3600 + minuto * 60 + segundo)
            ciclo_dia = (tempo_segundos / 86400) * 2 * math.pi
            hora_seno = math.sin(ciclo_dia)
            dia_semana = agora_dt.weekday()
            dia_seno = math.sin((dia_semana / 7) * 2 * math.pi)

            # ═══════════════════════════════════════════════════════════════
            # FEATURES - USANDO NORMALIZAÇÃO ROBUSTA (MELHORIA)
            # ═══════════════════════════════════════════════════════════════
            
            # Versão melhorada com normalização robusta
            # MACD normalizado por ATR (evita explosão em DOGE/SHIB)
            macd_norm = macd / (atr + 1e-9)
            macd_norm = max(-5.0, min(5.0, macd_norm))
            
            # Volatilidade como percentual
            vol_recente_pct = min(vol_recente * 100, 5.0)
            
            # Retornos em percentual com clamp
            ret_pct = max(-5.0, min(5.0, retorno * 100))
            ret5_pct = max(-10.0, min(10.0, retorno_5 * 100))
            ret10_pct = max(-15.0, min(15.0, retorno_10 * 100))
            
            # EMA spread normalizado
            ema_spread = (ema9 - ema21) / (preco + 1e-9) * 100
            ema_spread = max(-5.0, min(5.0, ema_spread))
            
            # Bollinger position
            bb_pos_clamped = max(-3.0, min(3.0, bb_pos))
            
            features = [
                ret_pct,                           # [0]  retorno 1-tick (%)
                ret5_pct,                          # [1]  retorno 5-tick (%)
                ret10_pct,                         # [2]  retorno 10-tick (%)
                ema_spread,                        # [3]  tendência EMA
                (rsi - 50) / 50,                   # [4]  RSI normalizado [-1, 1]
                macd_norm,                         # [5]  MACD/ATR (FIX B)
                bb_pos_clamped,                    # [6]  posição nas Bandas
                vol_recente_pct,                   # [7]  volatilidade % (FIX C)
                max(-2.0, min(2.0, padrao_score / 2)),  # [8]  score de padrão
                max(-1.0, min(1.0, memoria_score)),     # [9]  memória do universo
                max(-1.0, min(1.0, sync_score)),        # [10] sincronização cluster
                self.universo.memoria_global["delta_energia"] * 0.01,  # [11] delta energia
                hora_seno,                         # [12] hora do dia (sin)
                dia_seno,                          # [13] dia da semana (sin)
            ]

            # ── Pesos Adaptativos ─────────────────────────────────────────────
            if moeda not in self.pesos:
                self.pesos[moeda] = PesosAdaptativos(n_features=12)

            pesos = self.pesos[moeda]

            if moeda in self.features_anteriores and moeda in self.preco_anterior:
                target = (preco - self.preco_anterior[moeda]) / self.preco_anterior[moeda] * 100
                pred_anterior = pesos.update(self.features_anteriores[moeda], target)
                if (pred_anterior > 0) == (target > 0):
                    pesos.n_acertos += 1
                else:
                    pesos.n_erros += 1

            self.features_anteriores[moeda] = features
            self.preco_anterior[moeda]       = preco

            energia_cluster = sum(d["energia"] for d in minha_cluster if d["id"] != dado["id"])
            self.universo.forward(
                dado,
                energia_outro=energia_cluster if energia_cluster > 0 else features[0],
                distancia=features[3] * 100
            )

            # ── MenteTorch ─────────────────────────────────────────────────────
            mente = self._garantir_mente(moeda)

            if mente is not None:
                acc_por_horizonte = mente.accuracy_por_horizonte
                preds_raw = mente.forward(features)
                preds_percentual = [p * 5.0 for p in preds_raw]
                preds_para_verificar = preds_percentual.copy()

                # Proteção contra NaN
                tem_nan = False
                for i, val in enumerate(preds_percentual):
                    if math.isnan(val) or math.isinf(val):
                        preds_percentual[i] = 0.0
                        tem_nan = True

                if tem_nan:
                    print(f"[{moeda}] ⚠️ NaN detectado! Substituído por 0.")

                # ── Delayed Reward Buffer ──────────────────────────────────────
                if moeda not in self.buffers:
                    self.buffers[moeda] = DelayedRewardBuffer(HORIZONTES, self.timeframe)

                self.buffers[moeda].registrar(time.time(), preds_percentual.copy(), preco)

                recompensas_maduras = self.buffers[moeda].coletar_maduras(time.time(), preco)
                if recompensas_maduras:
                    for i, recompensa in recompensas_maduras:
                        try:
                            mente.aprender_horizonte(i, recompensa)
                        except Exception as e:
                            print(f"[PyTorch] Erro no aprendizado horizonte {i}: {e}")


                # ── Verificação real por horizonte (COM SUBSAMPLING) ────────────
                if moeda not in self.verificacoes:
                    self.verificacoes[moeda] = deque(maxlen=5000)
                    self.resultados_verificacao[moeda] = {
                        h: {"acertos": 0, "erros": 0, "total": 0} 
                        for h in HORIZONTES
                    }
                    if moeda not in self.historico_individual:
                        self.historico_individual[moeda] = {
                            h: deque(maxlen=1000) for h in HORIZONTES
                        }

                # NOVO: Registra snapshot com subsampling por horizonte
                snapshot = {
                    "time": int(time.time()),
                    "price": preco,
                    "preds": preds_para_verificar.copy(),
                }
                self.verificacoes[moeda].append(snapshot)

                agora_ts = int(time.time())
                resultados = self.resultados_verificacao[moeda]
                para_remover = []

                for v in self.verificacoes[moeda]:
                    tempo_passado = agora_ts - v["time"]
                    
                    for i, horizonte in enumerate(HORIZONTES):
                        chave = f"_vrf_{i}"
                        
                        # Só verifica se o horizonte transcorreu E se deve registrar (subsampling)
                        if tempo_passado >= horizonte and not v.get(chave):
                            
                            # SUBSAMPLING: só conta como trade se passou no filtro
                            if not self._deve_registrar_verificacao(moeda, horizonte):
                                v[chave] = True  # marca como verificado mas não conta
                                continue
                            
                            # Busca preço alvo (MAIS PRÓXIMO, não o primeiro)
                            preco_alvo = None
                            melhor_dist = float('inf')
                            
                            for v2 in self.verificacoes[moeda]:
                                dist = abs(v2["time"] - (v["time"] + horizonte))
                                if dist < melhor_dist and dist <= horizonte * 0.15:  # tolerância 15%
                                    melhor_dist = dist
                                    preco_alvo = v2["price"]
                            
                            if preco_alvo is None:
                                continue
                            
                            direcao_prevista = 1 if v["preds"][i] > 0 else -1
                            direcao_real = 1 if preco_alvo > v["price"] else -1
                            
                            if direcao_prevista == direcao_real:
                                resultados[horizonte]["acertos"] += 1
                            else:
                                resultados[horizonte]["erros"] += 1
                            resultados[horizonte]["total"] += 1
                            
                            v[chave] = True
                            
                            # Histórico individual
                            if moeda not in self.historico_individual:
                                self.historico_individual[moeda] = {
                                    h: deque(maxlen=1000) for h in HORIZONTES
                                }
                            if horizonte not in self.historico_individual[moeda]:
                                self.historico_individual[moeda][horizonte] = deque(maxlen=1000)
                            self.historico_individual[moeda][horizonte].append(
                                1 if direcao_prevista == direcao_real else 0
                            )
                    
                    # Remove expirados
                    todos_vrf = all(v.get(f"_vrf_{i}") for i in range(len(HORIZONTES)))
                    if todos_vrf or tempo_passado > 172800:
                        para_remover.append(v)

                for v in para_remover:
                    try:
                        self.verificacoes[moeda].remove(v)
                    except ValueError:
                        pass
               
              

                # ── Sinal consolidado ─────────────────────────────────────────
                curto = preds_percentual[:4] if len(preds_percentual) >= 4 else preds_percentual
                medio = preds_percentual[4:7] if len(preds_percentual) >= 7 else []
                longo = preds_percentual[7:] if len(preds_percentual) >= 8 else []
                
                media_curto = sum(curto) / len(curto) if curto else 0
                media_medio = sum(medio) / len(medio) if medio else media_curto
                media_longo = sum(longo) / len(longo) if longo else media_curto
                
                if (media_curto > 0.1 and media_medio > 0.05 and media_longo > 0) or \
                (media_curto < -0.1 and media_medio < -0.05 and media_longo < 0):
                    previsao = media_curto * 1.5
                else:
                    previsao = media_curto * 0.5
                
                dado["consenso_curto"] = round(media_curto, 4)
                dado["consenso_medio"] = round(media_medio, 4)
                dado["consenso_longo"] = round(media_longo, 4)

                # ── Salva predições por horizonte ─────────────────────────────
                for i, horizonte in enumerate(HORIZONTES):
                    nome_campo = f"previsao_{horizonte}s"
                    if i < len(preds_percentual):
                        dado[nome_campo] = preds_percentual[i]
                dado["predicoes_array"] = preds_percentual

                # ── Signal Engine ─────────────────────────────────────────────
                if hasattr(self, 'resultados_verificacao'):
                    self._signal_engine.avaliar(
                        moeda, preco, preds_percentual,
                        self.resultados_verificacao.get(moeda, {}),
                        dado.get("regime", "ranging"),
                        arquivo_disco=f"data/verificacoes/{moeda}.json",
                        acc_mente=acc_por_horizonte
                    )

            else:
                # Se a mente ainda não está pronta, usa o sinal dos pesos adaptativos
                previsao = pesos.forward(features)
                dado["previsao"] = previsao

            # ── Energia ─────────────────────────────────────────────────────────
            media_atual    = (preco + precos[-2]) / 2
            media_anterior = (precos[-2] + precos[-3]) / 2
            direcao_real   = 1 if media_atual > media_anterior else -1
            acertou   = (previsao > 0) == (direcao_real > 0)
            confianca = min(abs(previsao), 1.0)
            recompensa = (confianca if acertou else -confianca) * 2.0

            # ── SQL ───────────────────────────────────────────────────────────
            try:
                from Software.core.mind_sql import get_banco_sql
                banco_sql = get_banco_sql()
                banco_sql.registrar_performance(
                    mente_id=dado["id"],
                    symbol=moeda,
                    previsao=previsao,
                    preco_atual=preco,
                    direcao=1 if previsao > 0 else -1,
                    acertou=acertou,
                    reward=recompensa,
                    loss=abs(previsao - (1 if acertou else -1)) * 0.1,
                    regime=regime
                )
            except Exception as e:
                pass

            taxa = 0.15 if acertou else 0.25
            dado["energia"] += recompensa * taxa
            dado["energia"]  = max(0.5, min(10.0, dado["energia"]))
            if dado.get("tipo") == "crypto":
                dado["energia"] = max(5.0, min(10.0, dado["energia"]))

            # ── Pulso para cluster ────────────────────────────────────────────
            if abs(previsao) > 2.0 and len(minha_cluster) > 1:
                for outro_dado in minha_cluster:
                    if outro_dado["id"] == dado["id"]:
                        continue
                    sync = self.universo.sincronizacao(dado, outro_dado)
                    if sync > 0.4:
                        energia_pulso = min(dado["energia"] * 0.05, 0.3)
                        self.universo.enviar_pulso(dado["id"], outro_dado["id"], energia=energia_pulso)

            # ── Atualiza dado ─────────────────────────────────────────────────
            dado["previsao"] = previsao
            dado["regime"]   = regime
            dado["rsi"]      = round(rsi, 2)
            dado["atr"]      = round(atr, 4)
            dado["bb_pos"]   = round(bb_pos, 3)
            dado["accuracy"] = round(pesos.accuracy, 3)
            dado["ema9"]     = ema9
            dado["ema21"]    = ema21
            dado["sync"]     = round(sync_score, 3)
            dado["price"]    = preco
            dado["delta"]    = preco - precos[-2]

    # ─────────────────────────────────────────────────────────────────────────
    # SINAIS
    # ─────────────────────────────────────────────────────────────────────────

    def _gerar_sinais(self):
        sinais = []
        for moeda, id_dado in self.ids_cripto.items():
            dado = next((d for d in self.universo.dados if d["id"] == id_dado), None)
            if dado is None:
                continue
            energia  = dado.get("energia", 0)
            previsao = dado.get("previsao", 0)
            regime   = dado.get("regime", "?")
            accuracy = dado.get("accuracy", 0)
            rsi      = dado.get("rsi", 50)
            if previsao > 30:
                direcao = "STRONG BUY 🚀"
            elif previsao > 10:
                direcao = "BUY 📈"
            elif previsao < -30:
                direcao = "STRONG SELL 💥"
            elif previsao < -10:
                direcao = "SELL 📉"
            else:
                direcao = "HOLD ⏸"
            sinais.append((moeda, energia, previsao, direcao, regime, accuracy, rsi))
        sinais.sort(key=lambda x: abs(x[2]), reverse=True)
        resposta = ["📊 CRYPTO SIGNAL", ""]
        for moeda, energia, previsao, direcao, regime, accuracy, rsi in sinais:
            resposta.append(
                f"{moeda:10} | {direcao:18} | "
                f"score: {previsao:+.2f} | "
                f"acc: {accuracy:.0%} | "
                f"RSI: {rsi:.0f} | "
                f"regime: {regime}"
            )
        return resposta

    def _gerar_stats(self):
        linhas = ["📈 CRYPTO STATS", ""]
        for moeda, pesos in self.pesos.items():
            linhas.append(
                f"{moeda:10} | acc: {pesos.accuracy:.1%} | "
                f"loss: {pesos.loss_medio:.4f} | "
                f"ticks: {pesos.n_acertos + pesos.n_erros}"
            )
        return linhas if len(linhas) > 2 else ["Sem dados ainda"]

    # ─────────────────────────────────────────────────────────────────────────
    # SPAWN
    # ─────────────────────────────────────────────────────────────────────────

    def spawn_moedas(self, moedas):
        inicio = time.time()
        
        self.ids_cripto = {
            m: id_d
            for m, id_d in self.ids_cripto.items()
            if any(d["id"] == id_d for d in self.universo.dados)
        }

        print(f"[CRYPTO] 🔄 Buscando preços de todas as moedas...")
        todos_precos = pegar_todos_precos()

        if not todos_precos:
            return ["Erro ao buscar preços da Binance"]

        criados = []
        reutilizados = []
        recarregados = []

        for moeda in moedas:
            agente_existente = None
            for dado in self.universo.dados:
                if dado.get("symbol") == moeda and dado.get("tipo") == "crypto":
                    agente_existente = dado
                    break

            if agente_existente:
                id_agente = agente_existente["id"]
                self.ids_cripto[moeda] = id_agente

                with self._lock_mentes:
                    ja_tem = moeda in self.mentes_pytorch and self.mentes_pytorch[moeda] is not None

                if not ja_tem:
                    with self._lock_mentes:
                        self.mentes_pytorch[moeda] = None
                    self._executor.submit(self._init_mente_async, moeda, id_agente)

                reutilizados.append(f"{moeda} → ID {id_agente} (já ativa)")
                print(f"[CRYPTO] ✅ {moeda} já está ativa no universo")
                continue

            arquivo_pt = f"data/mentes_pytorch/mente_{moeda}.pt"
            tem_backup = os.path.exists(arquivo_pt)
            
            preco = todos_precos.get(moeda)
            if preco is None:
                print(f"[CRYPTO] ❌ {moeda} - preço não encontrado na Binance")
                continue

            dado = self.universo.criar_dado(
                tipo="energetico",
                pos=[preco / 1000, 300 + random.uniform(-50, 50)]
            )
            dado["history"]  = [{"time": int(time.time()), "price": preco}]
            dado["symbol"]   = moeda
            dado["price"]    = preco
            dado["delta"]    = 0.0
            dado["tipo"]     = "crypto"
            dado["energia"]  = min(10, max(3, math.log(preco + 1)))
            dado["previsao"] = 0.0
            dado["regime"]   = "ranging"
            dado["accuracy"] = 0.5
            dado["rsi"]      = 50.0
            dado["estado"]   = [
                random.uniform(0, 2 * math.pi),
                random.uniform(0.05, 0.3),
                random.uniform(0.6, 0.95)
            ]
            dado["memoria"]  = [{"tipo": "spawn_crypto", "preco_inicial": preco}]

            id_agente = dado["id"]
            self.ids_cripto[moeda] = id_agente
            self.pesos[moeda] = PesosAdaptativos()

            with self._lock_mentes:
                self.mentes_pytorch[moeda] = None
            self._executor.submit(self._init_mente_async, moeda, id_agente)

            if tem_backup:
                recarregados.append(f"{moeda} → ID {id_agente} @ ${preco:,.2f} (🧠 aprendizado restaurado)")
                print(f"[CRYPTO] ♻️ {moeda} recarregada do disco com aprendizado anterior")
            else:
                criados.append(f"{moeda} → ID {id_agente} @ ${preco:,.2f} (🆕 nova)")
                print(f"[CRYPTO] 🆕 {moeda} criada do zero (primeira vez)")

        resposta = []
        
        if recarregados:
            resposta.append("♻️ MOEDAS RECARREGADAS (aprendizado mantido do disco):")
            resposta.extend(recarregados)
        
        if reutilizados:
            resposta.append("✅ MOEDAS JÁ ATIVAS (nada foi alterado):")
            resposta.extend(reutilizados)
        
        if criados:
            resposta.append("🆕 MOEDAS NOVAS (primeira vez treinando):")
            resposta.extend(criados)

        tempo_total = time.time() - inicio
        print(f"[CRYPTO] ✅ spawn concluído em {tempo_total:.1f}s")
        print(f"[CRYPTO]    ♻️ {len(recarregados)} recarregadas | ✅ {len(reutilizados)} ativas | 🆕 {len(criados)} novas")

        return resposta if resposta else ["Nenhuma moeda carregada"]

    # ─────────────────────────────────────────────────────────────────────────
    # REMOÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def remover_moedas(self):
        print(f"[CRYPTO] ids_cripto ANTES: {list(self.ids_cripto.keys())}")

        if not self.ids_cripto:
            for dado in self.universo.dados:
                if dado.get("tipo") == "crypto":
                    self.ids_cripto[dado.get("symbol", "unknown")] = dado["id"]

        ids_para_remover = set(self.ids_cripto.values())
        novos_dados = [d for d in self.universo.dados if d["id"] not in ids_para_remover]
        self.universo.dados = novos_dados

        self.ids_cripto.clear()
        self.pesos.clear()
        self.features_anteriores.clear()
        self.preco_anterior.clear()
        self.precos.clear()
        with self._lock_mentes:
            self.mentes_pytorch.clear()

        print(f"[CRYPTO] Removidas {len(ids_para_remover)} moedas. Restam {len(self.universo.dados)} dados.")

    def remover_moedas_selecionadas(self, moedas_para_remover):
        removidas = []
        ids_para_remover = set()

        for moeda in moedas_para_remover:
            if moeda in self.ids_cripto:
                ids_para_remover.add(self.ids_cripto[moeda])
                removidas.append(moeda)
            else:
                for dado in self.universo.dados:
                    if dado.get("symbol") == moeda and dado.get("tipo") == "crypto":
                        ids_para_remover.add(dado["id"])
                        removidas.append(moeda)
                        self.ids_cripto[moeda] = dado["id"]
                        break

        if ids_para_remover:
            self.universo.dados = [d for d in self.universo.dados if d["id"] not in ids_para_remover]
            for moeda in removidas:
                self.ids_cripto.pop(moeda, None)
                self.pesos.pop(moeda, None)
                self.features_anteriores.pop(moeda, None)
                self.preco_anterior.pop(moeda, None)
                self.precos.pop(moeda, None)
                with self._lock_mentes:
                    self.mentes_pytorch.pop(moeda, None)

        return removidas

    # ─────────────────────────────────────────────────────────────────────────
    # RELATÓRIOS / STATS
    # ─────────────────────────────────────────────────────────────────────────

    def gerar_relatorio_desempenho(self):
        relatorio = []
        for moeda, id_dado in self.ids_cripto.items():
            mente_pt = self._garantir_mente(moeda)
            if mente_pt is not None:
                acertos = mente_pt.n_acertos[0] if mente_pt.n_acertos else 0
                erros   = mente_pt.n_erros[0]   if mente_pt.n_erros   else 0
                total   = acertos + erros
                acuracia = (acertos / total * 100) if total > 0 else 0
                confianca = min(100, acuracia)
                categoria = "recommended" if acuracia >= 55 else ("bad" if acuracia < 45 else "learning")
                relatorio.append({
                    "symbol": moeda, "acertos": acertos, "erros": erros,
                    "total": total, "acuracia": round(acuracia, 1),
                    "confianca": round(confianca, 1), "categoria": categoria,
                    "id": id_dado, "tipo": "pytorch_multi"
                })
            else:
                mente = self.universo.mentes.obter(id_dado)
                if mente is None:
                    continue
                total    = mente.n_acertos + mente.n_erros
                acuracia = (mente.n_acertos / total * 100) if total > 0 else 0
                confianca = min(100, acuracia)
                categoria = "recommended" if acuracia >= 55 else ("bad" if acuracia < 45 else "learning")
                relatorio.append({
                    "symbol": moeda, "acertos": mente.n_acertos, "erros": mente.n_erros,
                    "total": total, "acuracia": round(acuracia, 1),
                    "confianca": round(confianca, 1), "categoria": categoria,
                    "id": id_dado, "tipo": "classic"
                })
        relatorio.sort(key=lambda x: x["acuracia"], reverse=True)
        return relatorio

    def fetchAllAccuracies(self):
        cache = {}
        for moeda, id_dado in self.ids_cripto.items():
            mente = self._garantir_mente(moeda)
            if mente is not None:
                acertos = mente.n_acertos[0] if mente.n_acertos else 0
                erros   = mente.n_erros[0]   if mente.n_erros   else 0
                total   = acertos + erros
                acuracia = (acertos / total * 100) if total > 0 else 0
                cache[moeda] = {"acuracia": round(acuracia, 1), "acertos": acertos, "total": total}
            else:
                mente_cls = self.universo.mentes.obter(id_dado)
                if mente_cls:
                    total    = mente_cls.n_acertos + mente_cls.n_erros
                    acuracia = (mente_cls.n_acertos / total * 100) if total > 0 else 0
                    cache[moeda] = {"acuracia": round(acuracia, 1),
                                    "acertos": mente_cls.n_acertos, "total": total}
                else:
                    cache[moeda] = {"acuracia": 0, "acertos": 0, "total": 0}
        return cache

    def carregar_ultimas_moedas(self):
        try:
            import os
            arquivo = "data/ultimas_moedas.json"
            if os.path.exists(arquivo):
                with open(arquivo, "r") as f:
                    moedas = json.load(f)
                if moedas:
                    print(f"[CRYPTO] Carregando últimas moedas: {moedas}")
                    self.spawn_moedas(moedas)
                return moedas
        except Exception as e:
            print(f"[CRYPTO] Erro ao carregar últimas moedas: {e}")
        return []

    def salvar_ultimas_moedas(self):
        try:
            import os
            os.makedirs("data", exist_ok=True)
            with open("data/ultimas_moedas.json", "w") as f:
                json.dump(list(self.ids_cripto.keys()), f)
        except Exception as e:
            print(f"[CRYPTO] Erro ao salvar últimas moedas: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # LOOP API
    # ─────────────────────────────────────────────────────────────────────────

    def loop_api(self):
        print("[CRYPTO] 🔥 loop_api INICIADO")
        ultimo_salvar = time.time()

        while self.rodando_api:
            try:
                todos_precos = pegar_todos_precos()
                if todos_precos:
                    for moeda in list(self.ids_cripto.keys()):
                        preco = todos_precos.get(moeda)
                        if preco:
                            self.precos[moeda] = preco
                    print(f"[CRYPTO] ✅ Preços atualizados")
                else:
                    print("[CRYPTO] ❌ Erro ao buscar preços")

                with lock_universo:
                    self.update()

                agora = time.time()
                if agora - ultimo_salvar > 60:
                    print("[CRYPTO] 💾 Salvando modelos .pt...")
                    self._executor.submit(self._salvar_mentes_background)
                    ultimo_salvar = agora

            except Exception as e:
                print(f"[CryptoApp] loop_api erro: {e}")

            time.sleep(self.delay)

    def _salvar_mentes_background(self):
        try:
            with self._lock_mentes:
                mentes_snapshot = dict(self.mentes_pytorch)
            
            self.salvar_ultimas_moedas()
            self.salvar_resultados_verificacao()
            
            for moeda, mente in mentes_snapshot.items():
                if mente is not None:
                    try:
                        mente.salvar_com_nome(f"data/mentes_pytorch/mente_{moeda}.pt")
                    except Exception as e:
                        print(f"[CRYPTO] Erro ao salvar {moeda}: {e}")
            
            self.salvar_resultados_verificacao()
            print("[CRYPTO] 💾 Mentes salvas")
        except Exception as e:
            print(f"[CRYPTO] Erro: {e}")

    def salvar_resultados_verificacao(self):
        if not hasattr(self, 'resultados_verificacao'):
            return

        import os
        os.makedirs("data/verificacoes", exist_ok=True)

        for moeda, resultados_novos in self.resultados_verificacao.items():
            arquivo = f"data/verificacoes/{moeda}.json"

            dados_acumulados = {}
            if os.path.exists(arquivo):
                try:
                    with open(arquivo, "r") as f:
                        dados_acumulados = json.load(f)
                except:
                    dados_acumulados = {}

            for h, novos in resultados_novos.items():
                h_str = str(h)
                if h_str in dados_acumulados:
                    dados_acumulados[h_str]['acertos'] += novos['acertos']
                    dados_acumulados[h_str]['erros']   += novos['erros']
                    dados_acumulados[h_str]['total']   += novos['total']
                else:
                    dados_acumulados[h_str] = {
                        'acertos': novos['acertos'],
                        'erros':   novos['erros'],
                        'total':   novos['total']
                    }

            hist_moeda = self.historico_individual.get(moeda, {})
            for h, fila in hist_moeda.items():
                h_str = str(h)
                if h_str not in dados_acumulados:
                    dados_acumulados[h_str] = {'acertos': 0, 'erros': 0, 'total': 0}

                historico_disco = dados_acumulados[h_str].get('historico', [])
                historico_novo  = list(fila)
                historico_merged = (historico_disco + historico_novo)[-1000:]
                dados_acumulados[h_str]['historico'] = historico_merged

            # NOVO: limpa o que já foi persistido, para não duplicar no próximo save
            for h in hist_moeda:
                hist_moeda[h].clear()

            with open(arquivo, "w") as f:
                json.dump(dados_acumulados, f, indent=2)

        for moeda in self.resultados_verificacao:
            for h in self.resultados_verificacao[moeda]:
                self.resultados_verificacao[moeda][h] = {"acertos": 0, "erros": 0, "total": 0}

        print("[CRYPTO] 📊 Resultados acumulados salvos com sucesso")

    def medir_risk_reward(self):
        """Calcula o Risk/Reward real baseado nos dados de verificação"""
        import json
        import glob
        import os
        
        print("\n" + "=" * 65)
        print("📊 ANÁLISE DE RISK/REWARD POR HORIZONTE")
        print("=" * 65)
        
        arquivos = glob.glob("data/verificacoes/*.json")
        
        if not arquivos:
            print("❌ Nenhum arquivo de verificação encontrado.")
            return
        
        for arquivo in arquivos:
            moeda = os.path.basename(arquivo).replace(".json", "")
            
            with open(arquivo) as f:
                dados = json.load(f)
            
            print(f"\n💰 {moeda.replace('USDT', '')}")
            print(f"{'─' * 65}")
            print(f"{'Horizonte':<8} {'Trades':<8} {'Acurácia':<10} {'R/R Mínimo':<12} {'Lucro 1:2?':<12} {'Lucro 1:3?':<12}")
            print(f"{'─' * 65}")
            
            for h in ['5', '15', '30', '60', '300', '900', '1800', '3600']:
                if h in dados and dados[h]['total'] > 50:
                    d = dados[h]
                    acertos = d['acertos']
                    erros = d['erros']
                    total = d['total']
                    acuracia = round(acertos / total * 100, 1)
                    
                    if acertos > 0:
                        rr_minimo = round(erros / acertos, 2)
                    else:
                        rr_minimo = float('inf')
                    
                    lucro_1_2 = "✅ SIM" if acuracia > 33.3 else "❌ NÃO"
                    lucro_1_3 = "✅ SIM" if acuracia > 25 else "❌ NÃO"
                    
                    h_int = int(h)
                    if h_int < 60:
                        nome_h = f"{h_int}s"
                    elif h_int < 3600:
                        nome_h = f"{h_int//60}min"
                    else:
                        nome_h = f"{h_int//3600}h"
                    
                    print(f"{nome_h:<8} {total:<8} {acuracia}%{'':<5} 1:{rr_minimo}{'':<8} {lucro_1_2:<12} {lucro_1_3:<12}")
        
        print(f"\n{'=' * 65}")
        print("💡 R/R mínimo: o menor risco/recompensa para NÃO perder dinheiro")
        print("💡 Se R/R mínimo é 1:0.8, você pode arriscar 1 pra ganhar 0.8 e ainda empatar")
        print("💡 Se R/R mínimo é 1:1.2, você precisa arriscar 1 pra ganhar 1.2+ para lucrar")
        print("💡 R/R 1:2 = arriscar R$100 pra ganhar R$200")
        print("💡 Com 34% de acurácia + R/R 1:2 = LUCRO!")
        print("=" * 65)