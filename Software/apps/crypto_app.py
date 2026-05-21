import requests
import random
import math
import time
import threading
from collections import deque
from Software.core.universe_instance import lock_universo


def pegar_preco(simbolo):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}"
    try:
        data = requests.get(url).json()
        return float(data["price"])
    except Exception as e:
        print(f"[CryptoApp] Erro ao buscar {simbolo}: {e}")
        return None


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

    if corpo0 / amplitude0 < 0.1:
        score += 0

    sombra_baixa = c0["open"] - c0["low"] if c0["close"] >= c0["open"] else c0["close"] - c0["low"]
    sombra_alta  = c0["high"] - c0["close"] if c0["close"] >= c0["open"] else c0["high"] - c0["open"]
    if sombra_baixa > corpo0 * 2 and sombra_alta < corpo0 * 0.5:
        score += 1.5

    if sombra_alta > corpo0 * 2 and sombra_baixa < corpo0 * 0.5:
        score -= 1.5

    if (c1["close"] < c1["open"] and
        c0["close"] > c0["open"] and
        c0["open"] < c1["close"] and
        c0["close"] > c1["open"]):
        score += 2.0

    if (c1["close"] > c1["open"] and
        c0["close"] < c0["open"] and
        c0["open"] > c1["close"] and
        c0["close"] < c1["open"]):
        score -= 2.0

    if (c2["close"] > c2["open"] and
        c1["close"] > c1["open"] and
        c0["close"] > c0["open"] and
        c1["close"] > c2["close"] and
        c0["close"] > c1["close"]):
        score += 1.5

    if (c2["close"] < c2["open"] and
        c1["close"] < c1["open"] and
        c0["close"] < c0["open"] and
        c1["close"] < c2["close"] and
        c0["close"] < c1["close"]):
        score -= 1.5

    return score


# =============================================================================
#  PESOS ADAPTATIVOS — com correção de viés
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
#  CRYPTO APP
# =============================================================================

class CryptoApp:

    nome = "crypto_app"

    def __init__(self, universo):
        self.universo      = universo
        self.ultimo_update = 0
        self.delay         = 1
        self.ativo         = False
        self.ids_cripto    = {}
        self.precos        = {}
        self.rodando_api   = False
        self.timeframe     = 5

        self.pesos: dict[str, PesosAdaptativos] = {}
        self.features_anteriores: dict[str, list] = {}
        self.preco_anterior: dict[str, float] = {}

        self.lista_moedas = [
            "BTCUSDT",
            "ETHUSDT",
             "BNBUSDT",
             "XRPUSDT",
             "ADAUSDT",
             "SOLUSDT",
             "DOGEUSDT",
             "DOTUSDT",
             "MATICUSDT",
             "LTCUSDT"
        ]

    
    def remover_moedas(self):
        """Remove todas as moedas crypto - versão robusta"""
        
        print(f"[CRYPTO] ids_cripto ANTES: {list(self.ids_cripto.keys())}")
        
        # ⭐ Se ids_cripto está vazio, busca por tipo "crypto"
        if not self.ids_cripto:
            print("[CRYPTO] ids_cripto vazio! Buscando por tipo 'crypto'...")
            for dado in self.universo.dados:
                if dado.get("tipo") == "crypto":
                    self.ids_cripto[dado.get("symbol", "unknown")] = dado["id"]
            print(f"[CRYPTO] Encontrados {len(self.ids_cripto)} dados crypto")
        
        ids_para_remover = set(self.ids_cripto.values())
        print(f"[CRYPTO] IDs para remover: {ids_para_remover}")
        
        # ⭐ Remove os dados
        novos_dados = []
        for dado in self.universo.dados:
            if dado["id"] not in ids_para_remover:
                novos_dados.append(dado)
            else:
                print(f"[CRYPTO] Removendo dado ID {dado['id']} - {dado.get('symbol', 'unknown')}")
        
        self.universo.dados = novos_dados
        
        # ⭐ Limpa os registros locais
        self.ids_cripto.clear()
        self.pesos.clear()
        self.features_anteriores.clear()
        self.preco_anterior.clear()
        self.precos.clear()
        
        # ⭐ Salva forçadamente
        self.universo.salvar()
        
        print(f"[CRYPTO] Removidas {len(ids_para_remover)} moedas. Restam {len(self.universo.dados)} dados.")
    # ─────────────────────────────────────────────────────────────────────────
    # HANDLE
    # ─────────────────────────────────────────────────────────────────────────


    def handle(self, comando):

        if comando == "crypto start":
            self.ativo = True
            self.rodando_api = True
            t = threading.Thread(target=self.loop_api, daemon=True)
            t.start()
            return ["Crypto app started"]

        if comando == "crypto spawn all":
            return self.spawn_moedas(self.lista_moedas)

        if comando.startswith("crypto spawn"):
            partes = comando.split()
            moedas = [m.upper() for m in partes[2:]]
            return self.spawn_moedas(moedas)

        if comando == "crypto signal":
            return self._gerar_sinais()

        if comando == "crypto stop":
            self.ativo = False
            self.rodando_api = False
            self.remover_moedas()

            return ["Crypto app stopped and cleaned"]

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

        if comando.startswith("crypto "):
            return ["Unknown crypto command"]

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # UPDATE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def update(self):
        if not self.ativo:
            return

        agora = time.time()
        if agora - self.ultimo_update < self.delay:
            return
        self.ultimo_update = agora

        # Coleta dados ativos
        dados_ativos = {}
        for moeda, id_dado in self.ids_cripto.items():
            dado = next((d for d in self.universo.dados if d["id"] == id_dado), None)
            if dado is not None:
                dados_ativos[moeda] = dado

        # Detecta clusters
        clusters_universo = self.universo.detectar_clusters()
        cluster_por_id = {}
        for cluster in clusters_universo:
            for d in cluster:
                cluster_por_id[d["id"]] = cluster

        for moeda, dado in dados_ativos.items():

            preco = self.precos.get(moeda)
            if preco is None:
                continue

            # ── Histórico ────────────────────────────────────────────────────
            dado["history"].append({"time": int(time.time()), "price": preco})
            if len(dado["history"]) > 200:
                dado["history"].pop(0)

            precos = [p["price"] for p in dado["history"]]
            if len(precos) < 26:
                dado["price"] = preco
                continue

            # ── Candles ───────────────────────────────────────────────────────
            if "candles" not in dado:
                dado["candles"] = []

            atual_time = int(time.time())
            candle_time = atual_time - (atual_time % self.timeframe)

            if len(dado["candles"]) == 0 or dado["candles"][-1]["time"] != candle_time:
                # ⭐ NOVO CANDLE: começa com valores reais (sem spread artificial)
                dado["candles"].append({
                    "time":  candle_time,
                    "open":  preco,
                    "high":  preco,
                    "low":   preco,
                    "close": preco
                })
            else:
                c = dado["candles"][-1]
                c["high"]  = max(c["high"], preco)
                c["low"]   = min(c["low"],  preco)
                c["close"] = preco

                # Spread mínimo visível: 0.05% do preço
                if c["high"] - c["low"] < preco * 0.0005:
                    spread = preco * 0.0005
                    mid = (c["high"] + c["low"]) / 2
                    c["high"] = mid + spread / 2
                    c["low"]  = mid - spread / 2

            if len(dado["candles"]) > 300:
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

            # ── Sincronização com cluster ─────────────────────────────────────
            sync_score    = 0.0
            minha_cluster = cluster_por_id.get(dado["id"], [])
            for outro_dado in minha_cluster:
                if outro_dado["id"] == dado["id"]:
                    continue
                sync        = self.universo.sincronizacao(dado, outro_dado)
                sinal_outro = outro_dado.get("previsao", 0)
                sync_score += sync * sinal_outro * 0.3

            # ── Features ─────────────────────────────────────────────────────
            features = [
                retorno * 100,
                retorno_5 * 100,
                retorno_10 * 100,
                (ema9 - ema21) / (preco + 1e-9) * 100,
                (rsi - 50) / 50,
                macd / (preco + 1e-9) * 1000,
                bb_pos,
                vol_recente * 100,
                padrao_score / 2,
                memoria_score,
                sync_score,
                self.universo.memoria_global["delta_energia"] * 0.01,
            ]

            # ── Pesos adaptativos ─────────────────────────────────────────────
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

            # ── Forward do engine ─────────────────────────────────────────────
            energia_cluster = sum(d["energia"] for d in minha_cluster if d["id"] != dado["id"])
            score_universo  = self.universo.forward(
                dado,
                energia_outro=energia_cluster if energia_cluster > 0 else features[0],
                distancia=features[3] * 100
            )

            # ── Regime ───────────────────────────────────────────────────────
            confianca_regime = {
                "trend_up":   0.9,
                "trend_down": 0.9,
                "ranging":    0.5,
                "volatile":   0.3,
            }.get(regime, 0.7)

            # ── Previsão final ────────────────────────────────────────────────
            score_pesos  = pesos.forward(features)
            previsao_raw = (
                score_pesos    * 0.5 +
                score_universo * 0.3 +
                sync_score     * 0.2
            )
            previsao = previsao_raw * confianca_regime
            previsao = max(-5.0, min(5.0, previsao))

            print(f"[{moeda}] score_pesos={score_pesos:.3f} score_universo={score_universo:.3f} sync={sync_score:.3f}")
            print(f"[{moeda}] previsao={previsao:.3f} regime={regime} confianca={confianca_regime}")

            # ── Pulsos entre moedas ───────────────────────────────────────────
            if abs(previsao) > 2.0 and len(minha_cluster) > 1:
                for outro_dado in minha_cluster:
                    if outro_dado["id"] == dado["id"]:
                        continue
                    sync = self.universo.sincronizacao(dado, outro_dado)
                    if sync > 0.4:
                        energia_pulso = min(dado["energia"] * 0.05, 0.3)
                        self.universo.enviar_pulso(
                            dado["id"],
                            outro_dado["id"],
                            energia=energia_pulso
                        )

            # ── Aprendizado ───────────────────────────────────────────────────
            direcao_real = 1 if preco > precos[-2] else -1
            acertou      = (previsao > 0) == (direcao_real > 0)
            confianca    = min(abs(previsao) / 5.0, 1.0)
            recompensa   = confianca if acertou else -confianca

            self.universo.aprender(dado, recompensa)

            # ── Energia ───────────────────────────────────────────────────────
            taxa = 0.15 if acertou else 0.25
            dado["energia"] += recompensa * taxa
            dado["energia"]  = max(0.5, min(10.0, dado["energia"]))

            # ── Dados finais ──────────────────────────────────────────────────
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
            dado["delta"]    = preco - precos[-2]   # ← valor absoluto

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

            if previsao > 2:
                direcao = "STRONG BUY 🚀"
            elif previsao > 0.5:
                direcao = "BUY 📈"
            elif previsao < -2:
                direcao = "STRONG SELL 💥"
            elif previsao < -0.5:
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
        self.ids_cripto = {
            m: id_d
            for m, id_d in self.ids_cripto.items()
            if any(d["id"] == id_d for d in self.universo.dados)
        }
        criados = []

        for moeda in moedas:
            if moeda in self.ids_cripto:
                continue

            preco = pegar_preco(moeda)
            if preco is None:
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
            dado["memoria"].append({"tipo": "spawn_crypto", "preco_inicial": preco})

            self.ids_cripto[moeda] = dado["id"]
            self.pesos[moeda]      = PesosAdaptativos()

            criados.append(f"{moeda} → ID {dado['id']} @ ${preco:,.2f}")

        return ["Crypto data created:"] + criados if criados else ["No new crypto data created"]

    # ─────────────────────────────────────────────────────────────────────────
    # LOOP API
    # ─────────────────────────────────────────────────────────────────────────

    def loop_api(self):
        while self.rodando_api:
            print("[CryptoApp] Loop API rodando...")
            try:
                for moeda in list(self.ids_cripto.keys()):
                    preco = pegar_preco(moeda)
                    if preco is not None:
                        self.precos[moeda] = preco

                with lock_universo:
                    self.update()

            except Exception as e:
                print(f"[CryptoApp] loop_api erro: {e}")

            time.sleep(self.delay)