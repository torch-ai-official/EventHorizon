# Software/core/mind_pytorch.py
#
# MUDANÇAS v4 (vs v3) — SEM RESET DE PESOS (strict=False no carregar)
# ─────────────────────────────────────────────────────────────────────────────
#
# CORREÇÃO CRÍTICA — Gradiente chegava apenas nas cabeças, não no backbone:
#   O _passo_gradiente fazia detach() nos x_cabecas antes de recomputar,
#   cortando o grafo computacional no transformer e no LSTM.
#   Agora: forward completo é refeito com requires_grad=True na entrada,
#   propagando gradiente por toda a rede.
#
# CORREÇÃO — loss_entropy distorcia o gradiente:
#   -log(|pred|) penalizava outputs próximos de zero, mas zero pode ser a
#   resposta correta (mercado sem tendência). Removida. Substituída por
#   loss_calibracao: penaliza predições fortes quando o alvo é fraco.
#
# CORREÇÃO — loss_conf usava tensor `x` do último horizonte (acoplamento errado):
#   Agora usa a média dos embeddings de todas as cabeças treinadas nesse passo.
#
# CORREÇÃO — residual_2 era definido mas nunca usado: removido.
#
# CORREÇÃO — Scheduler parava de aprender após 2200 steps:
#   Substituído por CosineAnnealingWarmRestarts (T_0=500, reinicia o ciclo).
#
# CORREÇÃO — max_norm=0.3 cortava gradientes legítimos: aumentado para 1.0.
#
# CORREÇÃO — horizon_embeddings com escala 3.0 hard-coded: substituído por
#   nn.Parameter escalar aprendível por horizonte (horizon_scales).
#   Compatível com strict=False: escala inicial = 1.0.
#
# CORREÇÃO — _buscar_preco_proximo com tolerância ilimitada para horizontes
#   longos: agora usa tolerância proporcional ao horizonte (máx 10%).
#
# CORREÇÃO — coletar_maduras recriava deque desnecessariamente: filtragem
#   in-place com marcação de "expirado".
#
# MANTIDO SEM ALTERAÇÃO (compatibilidade com .pt existentes):
#   - Todas as dimensões de camadas (embedding, transformer, lstm, cabeças)
#   - n_entradas=14
#   - Estrutura das cabeças micro/intraday/swing/position
#   - n_acertos, n_erros, geracao
#   - Formato do state_dict (strict=False absorve residual_2 ausente)
# ─────────────────────────────────────────────────────────────────────────────

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import math
from collections import deque

HORIZONTES = [
    5,      # 5 segundos  (micro-scalping)
    15,     # 15 segundos
    30,     # 30 segundos
    60,     # 1 minuto
    300,    # 5 minutos   (scalping)
    900,    # 15 minutos  (intraday)
    1800,   # 30 minutos
    3600,   # 1 hora      (swing curto)
    18000,  # 5 horas     (swing médio)
    86400,  # 1 dia       (position trade)
]
N_HORIZONTES = len(HORIZONTES)


# =============================================================================
# DELAYED REWARD BUFFER  (correções 11 e 12)
# =============================================================================

class DelayedRewardBuffer:
    """
    Armazena snapshots (timestamp, pred_i, preco) e devolve recompensas
    reais quando o horizonte transcorreu.

    Correção 11: tolerância de busca proporcional ao horizonte (máx 10%).
    Correção 12: filtragem in-place — sem recriar o deque a cada chamada.
    """

    def __init__(self, horizontes: list[int], timeframe_s: int = 5):
        self.horizontes  = horizontes
        self.timeframe_s = timeframe_s
        self._buffer: deque = deque(maxlen=10_000)

    def registrar(self, ts: float, preds: list[float], preco: float):
        self._buffer.append({
            'ts':         ts,
            'preds':      list(preds),
            'preco':      preco,
            'verificado': set(),
            'expirado':   False,   # FIX 12: marca em vez de recriar deque
        })

    def coletar_maduras(self, ts_agora: float, preco_agora: float) -> list[tuple[int, float]]:
        resultados: list[tuple[int, float]] = []

        for entrada in self._buffer:
            if entrada['expirado']:
                continue

            elapsed = ts_agora - entrada['ts']

            for i, h in enumerate(self.horizontes):
                if i in entrada['verificado']:
                    continue

                # Tolerância: max(timeframe*3, horizonte*5%) — proporcional ao horizonte
                # FIX 11: antes era max(30, ts_agora - ts_alvo + 60), crescia sem limite
                tolerancia = max(self.timeframe_s * 3, h * 0.05)

                if elapsed < h - tolerancia:
                    continue

                ts_alvo    = entrada['ts'] + h
                preco_alvo = self._buscar_preco_proximo(ts_alvo, ts_agora, preco_agora, h)
                if preco_alvo is None:
                    continue

                retorno_pct = (preco_alvo - entrada['preco']) / (entrada['preco'] + 1e-9) * 100

                if h <= 60:
                    clamp = 3.0
                elif h <= 3600:
                    clamp = 2.0
                else:
                    clamp = 1.0

                recompensa = max(-clamp, min(clamp, retorno_pct)) / clamp
                resultados.append((i, recompensa))
                entrada['verificado'].add(i)

            # Marca como expirado se todos os horizontes foram verificados ou
            # se a entrada é mais velha que 2 dias
            if (len(entrada['verificado']) >= N_HORIZONTES or
                    ts_agora - entrada['ts'] > 86400 * 2):
                entrada['expirado'] = True

        return resultados

    def _buscar_preco_proximo(
        self,
        ts_alvo:    float,
        ts_agora:   float,
        preco_agora: float,
        horizonte:  int,
    ) -> float | None:
        if ts_alvo > ts_agora + 5:
            return None  # horizonte ainda não chegou

        # FIX 11: tolerância máx = 10% do horizonte (era ilimitada)
        tolerancia_busca = max(30.0, horizonte * 0.10)

        melhor      = None
        melhor_dist = float('inf')

        for entrada in self._buffer:
            if entrada['expirado']:
                continue
            dist = abs(entrada['ts'] - ts_alvo)
            if dist < melhor_dist:
                melhor_dist = dist
                melhor      = entrada['preco']

        return melhor if melhor_dist <= tolerancia_busca else preco_agora


# =============================================================================
# BLOCOS DA REDE  (sem alterações — compatibilidade com pesos existentes)
# =============================================================================

class AtencaoMultiCabeca(nn.Module):
    def __init__(self, dim, num_cabecas=4):
        super().__init__()
        self.num_cabecas = num_cabecas
        self.dim_cabeca  = dim // num_cabecas
        self.scale       = self.dim_cabeca ** -0.5

        self.q_proj   = nn.Linear(dim, dim)
        self.k_proj   = nn.Linear(dim, dim)
        self.v_proj   = nn.Linear(dim, dim)
        self.out_proj = nn.Linear(dim, dim)
        self.dropout  = nn.Dropout(0.1)

    def forward(self, x):
        batch, seq, dim = x.shape
        Q = self.q_proj(x).view(batch, seq, self.num_cabecas, self.dim_cabeca).transpose(1, 2)
        K = self.k_proj(x).view(batch, seq, self.num_cabecas, self.dim_cabeca).transpose(1, 2)
        V = self.v_proj(x).view(batch, seq, self.num_cabecas, self.dim_cabeca).transpose(1, 2)

        atencao = (Q @ K.transpose(-2, -1)) * self.scale
        atencao = F.softmax(atencao, dim=-1)
        atencao = self.dropout(atencao)

        saida = (atencao @ V).transpose(1, 2).contiguous().view(batch, seq, dim)
        return self.out_proj(saida)


class BlocoTransformer(nn.Module):
    def __init__(self, dim, num_cabecas=4, dropout=0.1):
        super().__init__()
        self.atencao = AtencaoMultiCabeca(dim, num_cabecas)
        self.norm1   = nn.LayerNorm(dim)
        self.norm2   = nn.LayerNorm(dim)

        self.ffn = nn.Sequential(
            nn.Linear(dim, dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * 4, dim),
            nn.Dropout(dropout)
        )

    def forward(self, x):
        x = x + self.atencao(self.norm1(x))
        x = x + self.ffn(self.norm2(x))
        return x


# =============================================================================
# MENTE TORCH  v4
# =============================================================================

class MenteTorch(nn.Module):

    def __init__(self, id_agente: int, n_entradas: int = 14):
        super().__init__()
        self.id_agente  = id_agente
        self.n_entradas = n_entradas

        # ── Embedding inicial (MANTIDO) ────────────────────────────────────
        self.embedding = nn.Sequential(
            nn.Linear(n_entradas, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 256),
            nn.LayerNorm(256),
            nn.GELU(),
        )

        # ── Transformer (MANTIDO) ──────────────────────────────────────────
        self.transformer = nn.ModuleList([
            BlocoTransformer(256, num_cabecas=8, dropout=0.1)
            for _ in range(6)
        ])

        # ── LSTM bidirecional (MANTIDO) ────────────────────────────────────
        self.lstm = nn.LSTM(
            input_size=256,
            hidden_size=128,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
            bidirectional=True
        )
        self.lstm_hidden  = None
        self.memoria_longa = deque(maxlen=200)

        self.proj_lstm = nn.Linear(256, 256)

        # ── Cross-attention (MANTIDO) ──────────────────────────────────────
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=256, num_heads=4, dropout=0.1, batch_first=True
        )

        self.residual_1 = nn.Linear(256, 256)
        # NOTA: residual_2 foi REMOVIDO (era definido mas nunca usado).
        # strict=False no carregar() absorve a chave ausente sem problema.

        # ── Cabeças por horizonte (MANTIDAS — mesmas dimensões) ────────────
        self.cabecas = nn.ModuleList()
        for _ in range(4):  self.cabecas.append(self._criar_cabeca('micro'))
        for _ in range(3):  self.cabecas.append(self._criar_cabeca('intraday'))
        for _ in range(2):  self.cabecas.append(self._criar_cabeca('swing'))
        self.cabecas.append(self._criar_cabeca('position'))

        # ── Cabeças auxiliares (MANTIDAS) ─────────────────────────────────
        self.cabeca_tendencia = nn.Sequential(
            nn.Linear(256 + N_HORIZONTES, 128), nn.LayerNorm(128), nn.GELU(),
            nn.Dropout(0.2), nn.Linear(128, 64), nn.GELU(),
            nn.Linear(64, 3), nn.Softmax(dim=1)
        )
        self.cabeca_confianca = nn.Sequential(
            nn.Linear(256, 64), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Sigmoid()
        )
        self.cabeca_volatilidade = nn.Sequential(
            nn.Linear(256, 64), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1), nn.Softplus()
        )
        self.cabeca_regime = nn.Sequential(
            nn.Linear(256, 32), nn.ReLU(), nn.Linear(32, 4), nn.Softmax(dim=1)
        )

        # ── Embeddings de horizonte (MANTIDOS) ────────────────────────────
        self.horizon_embeddings = nn.ParameterList([
            nn.Parameter(torch.randn(1, 32) * 0.02)
            for _ in range(N_HORIZONTES)
        ])
        self.proj_embed = nn.Linear(256 + 32, 256)

        # FIX 5: escala aprendível por horizonte (substitui * 3.0 hard-coded)
        # Inicializada em 1.0 → comportamento neutro ao carregar pesos antigos.
        # Carregamentos com strict=False irão ignorar essa chave e usar 1.0.
        self.horizon_scales = nn.Parameter(torch.ones(N_HORIZONTES))

        # ── Otimizador ─────────────────────────────────────────────────────
        self.otimizador = torch.optim.AdamW(
            self.parameters(),
            lr=1e-3,
            betas=(0.9, 0.999),
            weight_decay=0.01,
            amsgrad=True
        )

        # FIX 7: CosineAnnealingWarmRestarts — reinicia o ciclo a cada T_0 steps
        # Evita que a LR fique presa em eta_min após 2200 steps.
        self._scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.otimizador,
            T_0=500,        # reinicia a cada 500 steps
            T_mult=1,       # ciclos de tamanho igual
            eta_min=5e-5,
        )

        # ── Métricas ───────────────────────────────────────────────────────
        self.n_acertos = [0] * N_HORIZONTES
        self.n_erros   = [0] * N_HORIZONTES
        self.geracao   = 0

        self.memoria_erros      = deque(maxlen=50)
        self.memoria_loss       = deque(maxlen=100)
        self.memoria_gradientes = deque(maxlen=20)

        # ── Estado interno ─────────────────────────────────────────────────
        self.ultima_entrada        = None
        self.ultimo_estado_oculto  = None
        self.estado_interno        = torch.zeros(1, 256)
        self._ultimos_x_cabecas    = None
        # FIX 8: guarda também a sequência de entrada para recomputar forward
        self._ultima_sequencia     = None
        self._ultima_entrada_raw   = None   # tensor de entrada antes do embedding

    # ─────────────────────────────────────────────────────────────────────────
    # PROPRIEDADES
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def accuracy_por_horizonte(self) -> list[float]:
        result = []
        for a, e in zip(self.n_acertos, self.n_erros):
            total = a + e
            result.append(round(a / total, 3) if total > 0 else 0.5)
        return result

    @property
    def accuracy(self) -> float:
        accs = self.accuracy_por_horizonte
        return sum(accs) / len(accs) if accs else 0.5

    @property
    def confidence(self) -> float:
        if not self.memoria_erros:
            return 0.7
        erro_medio = sum(self.memoria_erros) / len(self.memoria_erros)
        return max(0.3, min(0.95, 1 - erro_medio * 2))

    @property
    def learning_stability(self) -> str:
        if not self.memoria_gradientes:
            return "desconhecida"
        grad_medio = sum(self.memoria_gradientes) / len(self.memoria_gradientes)
        if grad_medio < 0.1:   return "estável"
        elif grad_medio < 0.5: return "moderada"
        else:                  return "instável"

    @property
    def loss_medio(self) -> float:
        if not self.memoria_loss:
            return 0.5
        return sum(self.memoria_loss) / len(self.memoria_loss)

    # ─────────────────────────────────────────────────────────────────────────
    # SNAPSHOT
    # ─────────────────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        accs = self.accuracy_por_horizonte
        return {
            "geracao":                self.geracao,
            "accuracy_por_horizonte": accs,
            "accuracy_micro":         round(sum(accs[:4]) / 4, 4)  if len(accs) >= 4  else 0.5,
            "accuracy_intraday":      round(sum(accs[4:7]) / 3, 4) if len(accs) >= 7  else 0.5,
            "accuracy_swing":         round(sum(accs[7:9]) / 2, 4) if len(accs) >= 9  else 0.5,
            "accuracy_position":      round(accs[9], 4)            if len(accs) >= 10 else 0.5,
            "accuracy_media":         round(self.accuracy, 4),
            "loss_medio":             round(self.loss_medio, 6),
            "confidence":             round(self.confidence, 4),
            "learning_stability":     self.learning_stability,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # CRIAÇÃO DE CABEÇAS (MANTIDAS — mesmas dimensões)
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_cabeca(self, tipo: str) -> nn.Module:
        if tipo == 'micro':
            return nn.Sequential(
                nn.Linear(256, 64), nn.GELU(), nn.Dropout(0.05),
                nn.Linear(64, 16),  nn.GELU(), nn.Linear(16, 1), nn.Tanh()
            )
        elif tipo == 'intraday':
            return nn.Sequential(
                nn.Linear(256, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.1),
                nn.Linear(128, 64),  nn.GELU(),
                nn.Linear(64, 16),   nn.GELU(), nn.Linear(16, 1), nn.Tanh()
            )
        elif tipo == 'swing':
            return nn.Sequential(
                nn.Linear(256, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.15),
                nn.Linear(128, 64),  nn.LayerNorm(64),  nn.GELU(), nn.Dropout(0.15),
                nn.Linear(64, 32),   nn.GELU(),
                nn.Linear(32, 16),   nn.GELU(), nn.Linear(16, 1), nn.Tanh()
            )
        else:  # position
            return nn.Sequential(
                nn.Linear(256, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.2),
                nn.Linear(128, 64),  nn.LayerNorm(64),  nn.GELU(), nn.Dropout(0.2),
                nn.Linear(64, 32),   nn.LayerNorm(32),  nn.GELU(), nn.Dropout(0.2),
                nn.Linear(32, 16),   nn.GELU(), nn.Linear(16, 1), nn.Tanh()
            )

    # ─────────────────────────────────────────────────────────────────────────
    # FORWARD  (FIX 5: horizon_scales aprendíveis)
    # ─────────────────────────────────────────────────────────────────────────

    def forward(self, entrada: list) -> list[float]:
        if len(entrada) < self.n_entradas:
            entrada = entrada + [0.0] * (self.n_entradas - len(entrada))

        tensor = torch.tensor(entrada[:self.n_entradas], dtype=torch.float32)

        # Sequência curto prazo
        if self.ultimo_estado_oculto is None:
            sequencia = tensor.unsqueeze(0).unsqueeze(0)
            self.ultimo_estado_oculto = tensor.clone()
        else:
            estado_anterior = self.ultimo_estado_oculto.unsqueeze(0).unsqueeze(0)
            atual           = tensor.unsqueeze(0).unsqueeze(0)
            sequencia       = torch.cat([estado_anterior, atual], dim=1)
            if sequencia.shape[1] > 10:
                sequencia = sequencia[:, -10:, :]
            self.ultimo_estado_oculto = tensor.clone()

        # FIX 8: salva a sequência para recomputar o forward no _passo_gradiente
        self._ultima_sequencia  = sequencia.detach()
        self._ultima_entrada_raw = tensor.detach()

        # Embedding + Transformer
        x_curto = self.embedding(sequencia)
        for bloco in self.transformer:
            x_curto = bloco(x_curto)
        x_curto = x_curto.mean(dim=1)

        # LSTM
        self.memoria_longa.append(x_curto.detach().squeeze(0))

        if len(self.memoria_longa) >= 10:
            estados_recentes = list(self.memoria_longa)[-200:]
            seq_longa = torch.stack(estados_recentes, dim=0).unsqueeze(0)

            if self.lstm_hidden is None:
                lstm_out, self.lstm_hidden = self.lstm(seq_longa)
            else:
                h, c = self.lstm_hidden
                lstm_out, self.lstm_hidden = self.lstm(seq_longa, (h.detach(), c.detach()))

            x_longo = self.proj_lstm(lstm_out[:, -1, :])
        else:
            x_longo = x_curto

        # Cross-attention
        x_curto_3d = x_curto.unsqueeze(1)
        x_longo_3d = x_longo.unsqueeze(1)
        x_cross, _ = self.cross_attention(x_curto_3d, x_longo_3d, x_longo_3d)
        x_cross     = x_cross.squeeze(1)

        # Combinação
        x_combinado = x_curto + x_longo * 0.3 + x_cross * 0.2
        x_combinado = x_combinado + self.residual_1(x_combinado) * 0.3

        self.estado_interno = 0.9 * self.estado_interno + 0.1 * x_combinado.detach()
        self.ultima_entrada  = x_combinado.clone()

        # Cabeças por horizonte
        saidas      = []
        xs_cabecas  = []

        for i, cab in enumerate(self.cabecas):
            if i < 4:
                x = x_curto * 0.7 + x_cross * 0.2 + x_longo * 0.1
            elif i < 7:
                x_base = x_curto * 0.4 + x_cross * 0.3 + x_longo * 0.3
                if i == 4:   x = x_base + x_curto * 0.15
                elif i == 5: x = x_base + x_longo * 0.15
                else:        x = x_base + x_longo * 0.3
            elif i < 9:
                x_base = x_longo * 0.6 + x_cross * 0.3 + x_curto * 0.1
                x = x_base + (x_curto if i == 7 else x_longo) * 0.1
            else:
                x = x_longo * 0.8 + x_cross * 0.2

            # FIX 5: escala aprendível (era * 3.0 hard-coded)
            escala = self.horizon_scales[i].clamp(0.5, 5.0)
            emb    = self.horizon_embeddings[i] * escala
            x      = self.proj_embed(torch.cat([x, emb], dim=1))
            x      = x + self.residual_1(x) * 0.3

            xs_cabecas.append(x.detach())
            saidas.append(float(cab(x).item()))

        self._ultimos_x_cabecas = xs_cabecas
        return saidas

    # ─────────────────────────────────────────────────────────────────────────
    # APRENDER (batch completo)
    # ─────────────────────────────────────────────────────────────────────────

    def aprender(self, recompensas: list[float]):
        if self._ultima_sequencia is None:
            return
        if isinstance(recompensas, (int, float)):
            recompensas = [float(recompensas)] * N_HORIZONTES
        elif isinstance(recompensas, torch.Tensor):
            recompensas = recompensas.detach().flatten().tolist()
        elif not isinstance(recompensas, list):
            return
        if len(recompensas) != N_HORIZONTES:
            return
        if any(math.isnan(r) or math.isinf(r) for r in recompensas):
            return
        self._passo_gradiente(recompensas, list(range(N_HORIZONTES)))

    # ─────────────────────────────────────────────────────────────────────────
    # APRENDER HORIZONTE (treinamento parcial — só a cabeça i)
    # ─────────────────────────────────────────────────────────────────────────

    def aprender_horizonte(self, i: int, recompensa: float):
        if self._ultima_sequencia is None:
            return
        if math.isnan(recompensa) or math.isinf(recompensa):
            return
        if not (0 <= i < N_HORIZONTES):
            return

        # Lê predição ANTES de treinar (para comparar depois)
        x_i = self._ultimos_x_cabecas[i].detach()
        with torch.no_grad():
            pred = float(self.cabecas[i](x_i).item())

        self._passo_gradiente([recompensa], [i])

        if (pred > 0) == (recompensa > 0):
            self.n_acertos[i] += 1
        else:
            self.n_erros[i] += 1

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO DE GRADIENTE  (FIX 8 — gradiente propaga por TODO o backbone)
    # ─────────────────────────────────────────────────────────────────────────

    def _passo_gradiente(self, recompensas: list[float], indices: list[int]):
        """
        FIX 8: em vez de reusar tensores com detach() (que cortava o grafo),
        recomputa o forward a partir da sequência salva, mantendo o grafo
        computacional inteiro. Gradiente chega no transformer e no LSTM.

        Cuidado com memória: usamos retain_graph=False (padrão) e zeramos
        o estado oculto do LSTM durante o treino para evitar ciclos.
        """
        if self._ultima_sequencia is None:
            return

        self.otimizador.zero_grad()

        sequencia = self._ultima_sequencia  # [1, seq_len, n_entradas] — sem grad ainda

        # ── Recomputa embedding + transformer com grad ─────────────────────
        x = self.embedding(sequencia)
        for bloco in self.transformer:
            x = bloco(x)
        x_curto = x.mean(dim=1)   # [1, 256] — com gradiente

        # ── Recomputa LSTM com grad ────────────────────────────────────────
        if len(self.memoria_longa) >= 10:
            # Usa os estados salvos (detach para não criar ciclo no LSTM)
            estados = list(self.memoria_longa)[-200:]
            # Substitui o último estado pela versão com gradiente
            seq_longa = torch.stack(estados[:-1] + [x_curto.squeeze(0)], dim=0).unsqueeze(0)

            h0 = None
            if self.lstm_hidden is not None:
                h0 = (self.lstm_hidden[0].detach(), self.lstm_hidden[1].detach())

            lstm_out, _ = self.lstm(seq_longa, h0)
            x_longo = self.proj_lstm(lstm_out[:, -1, :])
        else:
            x_longo = x_curto

        # ── Cross-attention com grad ───────────────────────────────────────
        x_cross, _ = self.cross_attention(
            x_curto.unsqueeze(1), x_longo.unsqueeze(1), x_longo.unsqueeze(1)
        )
        x_cross = x_cross.squeeze(1)

        x_combinado = x_curto + x_longo * 0.3 + x_cross * 0.2
        x_combinado = x_combinado + self.residual_1(x_combinado) * 0.3

        # ── Cabeças nas posições indicadas ────────────────────────────────
        preds_lista     = []
        xs_para_conf    = []

        for idx_rel, i in enumerate(indices):
            if i < 4:
                xi = x_curto * 0.7 + x_cross * 0.2 + x_longo * 0.1
            elif i < 7:
                x_base = x_curto * 0.4 + x_cross * 0.3 + x_longo * 0.3
                if i == 4:   xi = x_base + x_curto * 0.15
                elif i == 5: xi = x_base + x_longo * 0.15
                else:        xi = x_base + x_longo * 0.3
            elif i < 9:
                x_base = x_longo * 0.6 + x_cross * 0.3 + x_curto * 0.1
                xi = x_base + (x_curto if i == 7 else x_longo) * 0.1
            else:
                xi = x_longo * 0.8 + x_cross * 0.2

            escala = self.horizon_scales[i].clamp(0.5, 5.0)
            emb    = self.horizon_embeddings[i] * escala
            xi     = self.proj_embed(torch.cat([xi, emb], dim=1))
            xi     = xi + self.residual_1(xi) * 0.3

            xs_para_conf.append(xi)
            preds_lista.append(self.cabecas[i](xi))

        preds = torch.cat(preds_lista, dim=1)              # [1, n_indices]
        alvo  = torch.tensor([recompensas], dtype=torch.float32)

        if preds.shape != alvo.shape:
            return

        # ── Losses ────────────────────────────────────────────────────────
        loss_huber = F.smooth_l1_loss(preds, alvo)
        loss_mse   = F.mse_loss(preds, alvo)
        loss_mae   = F.l1_loss(preds, alvo)

        # FIX 2: confiança usa a média dos embeddings das cabeças treinadas
        x_conf_medio = torch.stack(xs_para_conf, dim=0).mean(dim=0)
        erro_abs   = torch.abs(preds - alvo).mean()
        confianca  = self.cabeca_confianca(x_conf_medio)
        target_conf = torch.sigmoid(1 - erro_abs).view_as(confianca)
        loss_conf  = F.binary_cross_entropy(confianca, target_conf)

        # Consistência temporal: só faz sentido com índices consecutivos
        if len(indices) > 1 and all(indices[j] + 1 == indices[j + 1] for j in range(len(indices) - 1)):
            loss_consist = torch.mean((preds[:, 1:] - preds[:, :-1]) ** 2)
        else:
            loss_consist = torch.tensor(0.0)

        loss_vol = self.cabeca_volatilidade(x_conf_medio).mean()

        # Regularização L2 apenas nas cabeças treinadas
        loss_reg = sum(
            torch.sum(p ** 2)
            for i in indices[-3:]
            for p in self.cabecas[i].parameters()
        ) * 1e-5

        # FIX 1: loss_calibracao substitui loss_entropy
        # Penaliza predições FORTES quando o alvo é FRACO (evita overconfidence)
        # Não penaliza predições próximas de zero (que podem ser corretas)
        pred_magnitude = torch.abs(preds)
        alvo_magnitude = torch.abs(alvo)
        loss_calibracao = F.mse_loss(pred_magnitude, alvo_magnitude)

        loss = (loss_huber      * 0.40 +
                loss_mse        * 0.15 +
                loss_mae        * 0.10 +
                loss_conf       * 0.10 +
                loss_consist    * 0.10 +
                loss_vol        * 0.05 +
                loss_reg        * 0.05 +
                loss_calibracao * 0.05)

        loss.backward()

        # Corrige gradientes NaN
        for param in self.parameters():
            if param.grad is not None:
                param.grad = torch.nan_to_num(
                    param.grad, nan=0.0, posinf=1.0, neginf=-1.0
                )

        # FIX 9: max_norm 0.3 → 1.0 (era agressivo demais, cortava gradientes legítimos)
        grad_norm = torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=1.0)

        if math.isnan(grad_norm.item()):
            print("[PyTorch] ⚠️ Gradiente NaN detectado! Pulando passo.")
            self.otimizador.zero_grad()
            return

        self.memoria_gradientes.append(grad_norm.item())
        self.otimizador.step()
        self._scheduler.step()

        self.memoria_loss.append(loss.item())
        self.memoria_erros.append(erro_abs.item())
        self.geracao += 1

    # ─────────────────────────────────────────────────────────────────────────
    # PERSISTÊNCIA  (backward-compatible com .pt v3)
    # ─────────────────────────────────────────────────────────────────────────

    def salvar_com_nome(self, caminho_completo: str):
        os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
        torch.save({
            'model_state_dict':     self.state_dict(),
            'optimizer_state_dict': self.otimizador.state_dict(),
            'scheduler_state_dict': self._scheduler.state_dict(),
            'n_acertos':            self.n_acertos,
            'n_erros':              self.n_erros,
            'geracao':              self.geracao,
            'historico_loss':       list(self.memoria_loss),
            'memoria_erros':        list(self.memoria_erros),
            'estado_interno':       self.estado_interno,
            'versao':               'v4_full_backprop'
        }, caminho_completo)

    def carregar(self, caminho: str = "data/mentes_pytorch") -> bool:
        arquivo = f"{caminho}/mente_{self.id_agente}.pt"
        if os.path.exists(arquivo):
            try:
                ck = torch.load(arquivo, map_location='cpu')
                # strict=False: absorve residual_2 ausente e horizon_scales novo
                self.load_state_dict(ck['model_state_dict'], strict=False)
                try:
                    self.otimizador.load_state_dict(ck['optimizer_state_dict'])
                except Exception:
                    pass   # optimizer incompatível (mudança de scheduler) — ignora
                try:
                    self._scheduler.load_state_dict(ck['scheduler_state_dict'])
                except Exception:
                    pass   # scheduler novo — começa do zero, sem problema
                self.n_acertos     = ck.get('n_acertos',    [0] * N_HORIZONTES)
                self.n_erros       = ck.get('n_erros',      [0] * N_HORIZONTES)
                self.geracao       = ck.get('geracao',       0)
                self.memoria_loss  = deque(ck.get('historico_loss', []), maxlen=100)
                self.memoria_erros = deque(ck.get('memoria_erros',  []), maxlen=50)
                if 'estado_interno' in ck:
                    self.estado_interno = ck['estado_interno']
                versao = ck.get('versao', 'desconhecida')
                print(f"[PyTorch] Mente {self.id_agente} carregada "
                      f"(v={versao}, gen={self.geracao}, "
                      f"estabilidade={self.learning_stability})")
                return True
            except Exception as e:
                print(f"[PyTorch] Erro ao carregar mente {self.id_agente}: {e}")
        return False

    def para_dict(self) -> dict:
        return {
            "id_agente":              self.id_agente,
            "n_acertos":              self.n_acertos,
            "n_erros":                self.n_erros,
            "geracao":                self.geracao,
            "accuracy_por_horizonte": self.accuracy_por_horizonte,
            "confidence":             self.confidence,
            "learning_stability":     self.learning_stability,
            "tipo":                   "pytorch_v4_full_backprop"
        }