# Software/core/mind_pytorch.py

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import math
from collections import deque

# 10 HORIZONTES - do micro-scalping ao swing trade
HORIZONTES = [
    5,      # 5 segundos (micro-scalping)
    15,     # 15 segundos
    30,     # 30 segundos
    60,     # 1 minuto
    300,    # 5 minutos (scalping)
    900,    # 15 minutos (intraday)
    1800,   # 30 minutos
    3600,   # 1 hora (swing curto)
    18000,  # 5 horas (swing médio)
    86400,  # 1 dia (position trade)
]
N_HORIZONTES = len(HORIZONTES)


class AtencaoMultiCabeca(nn.Module):
    def __init__(self, dim, num_cabecas=4):
        super().__init__()
        self.num_cabecas = num_cabecas
        self.dim_cabeca = dim // num_cabecas
        self.scale = self.dim_cabeca ** -0.5

        self.q_proj = nn.Linear(dim, dim)
        self.k_proj = nn.Linear(dim, dim)
        self.v_proj = nn.Linear(dim, dim)
        self.out_proj = nn.Linear(dim, dim)
        self.dropout = nn.Dropout(0.1)

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
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

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


class MenteTorch(nn.Module):

    def __init__(self, id_agente: int, n_entradas: int = 14):
        super().__init__()
        self.id_agente = id_agente
        self.n_entradas = n_entradas

        # Embedding inicial
        self.embedding = nn.Sequential(
            nn.Linear(n_entradas, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 256),
            nn.LayerNorm(256),
            nn.GELU(),
        )

        # Transformer para padrões de curto prazo
        self.transformer = nn.ModuleList([
            BlocoTransformer(256, num_cabecas=8, dropout=0.1)
            for _ in range(6)
        ])

        # LSTM para memória de longo prazo (bidirecional)
        self.lstm = nn.LSTM(
            input_size=256,
            hidden_size=128,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
            bidirectional=True
        )
        self.lstm_hidden = None

        self.memoria_longa = deque(maxlen=200)

        # Projeção do LSTM (256 porque bidirecional: 128*2)
        self.proj_lstm = nn.Linear(256, 256)

        # Atenção cross-scale (curto prazo <-> longo prazo)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=256,
            num_heads=4,
            dropout=0.1,
            batch_first=True
        )

        self.residual_1 = nn.Linear(256, 256)
        self.residual_2 = nn.Linear(256, 128)

        # Cabeças com complexidade progressiva por horizonte
        self.cabecas = nn.ModuleList()

        # Micro-scalping (5s-60s): redes leves
        for _ in range(4):
            self.cabecas.append(self._criar_cabeca('micro'))

        # Scalping/Intraday (5m-30m): redes médias
        for _ in range(3):
            self.cabecas.append(self._criar_cabeca('intraday'))

        # Swing trade (1h-5h): redes mais profundas
        for _ in range(2):
            self.cabecas.append(self._criar_cabeca('swing'))

        # Position trade (1d): rede profunda com mais dropout
        self.cabecas.append(self._criar_cabeca('position'))

        # Cabeça de tendência global
        self.cabeca_tendencia = nn.Sequential(
            nn.Linear(256 + N_HORIZONTES, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Linear(64, 3),
            nn.Softmax(dim=1)
        )

        self.cabeca_confianca = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

        self.cabeca_volatilidade = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Softplus()
        )

        # Cabeça de regime de mercado
        self.cabeca_regime = nn.Sequential(
            nn.Linear(256, 32),
            nn.ReLU(),
            nn.Linear(32, 4),  # trend_up, trend_down, ranging, volatile
            nn.Softmax(dim=1)
        )

        self.otimizador = torch.optim.AdamW(
            self.parameters(),
            lr=0.001,
            betas=(0.9, 0.999),
            weight_decay=0.01,
            amsgrad=True
        )
        self.warmup_steps = 200
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.otimizador,
            T_max=500,
            eta_min=1e-5
        )

        self.n_acertos = [0] * N_HORIZONTES
        self.n_erros = [0] * N_HORIZONTES
        self.geracao = 0

        self.memoria_erros = deque(maxlen=50)
        self.memoria_loss = deque(maxlen=100)
        self.memoria_gradientes = deque(maxlen=20)

        self.ultima_entrada = None
        self.ultimo_estado_oculto = None
        self.estado_interno = torch.zeros(1, 256)
        self.horizon_embeddings = nn.ParameterList([
            nn.Parameter(torch.randn(1, 32) * 0.02)
            for _ in range(N_HORIZONTES)
        ])

        self.proj_embed = nn.Linear(256 + 32, 256)

        self._ultimos_x_cabecas = None

        print(f"[PyTorch] Mente {id_agente} carregada")
        print(f"[PyTorch]    Horizontes: {N_HORIZONTES} | Transformer: 6 camadas | LSTM: bidirecional")
        print(f"[PyTorch]    Cabeças: micro(4) + intraday(3) + swing(2) + position(1)")

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
        if grad_medio < 0.1:
            return "estável"
        elif grad_medio < 0.3:
            return "moderada"
        else:
            return "instável"

    @property
    def loss_medio(self) -> float:
        if not self.memoria_loss:
            return 0.5
        return sum(self.memoria_loss) / len(self.memoria_loss)

    # ─────────────────────────────────────────────────────────────────────────
    # SNAPSHOT (para comparar antes/depois do treinamento)
    # ─────────────────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Retorna métricas atuais para comparação antes/depois."""
        return {
            "geracao": self.geracao,
            "accuracy_por_horizonte": self.accuracy_por_horizonte,
            "accuracy_media": round(self.accuracy, 4),
            "loss_medio": round(self.loss_medio, 6),
            "confidence": round(self.confidence, 4),
            "learning_stability": self.learning_stability,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # CRIAÇÃO DE CABEÇAS
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_cabeca(self, tipo: str) -> nn.Module:
        if tipo == 'micro':
            return nn.Sequential(
                nn.Linear(256, 64),
                nn.GELU(),
                nn.Dropout(0.05),
                nn.Linear(64, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Tanh()
            )
        elif tipo == 'intraday':
            return nn.Sequential(
                nn.Linear(256, 128),
                nn.LayerNorm(128),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(128, 64),
                nn.GELU(),
                nn.Linear(64, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Tanh()
            )
        elif tipo == 'swing':
            return nn.Sequential(
                nn.Linear(256, 128),
                nn.LayerNorm(128),
                nn.GELU(),
                nn.Dropout(0.15),
                nn.Linear(128, 64),
                nn.LayerNorm(64),
                nn.GELU(),
                nn.Dropout(0.15),
                nn.Linear(64, 32),
                nn.GELU(),
                nn.Linear(32, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Tanh()
            )
        else:  # position
            return nn.Sequential(
                nn.Linear(256, 128),
                nn.LayerNorm(128),
                nn.GELU(),
                nn.Dropout(0.25),
                nn.Linear(128, 64),
                nn.LayerNorm(64),
                nn.GELU(),
                nn.Dropout(0.25),
                nn.Linear(64, 32),
                nn.LayerNorm(32),
                nn.GELU(),
                nn.Dropout(0.25),
                nn.Linear(32, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Tanh()
            )

    # ─────────────────────────────────────────────────────────────────────────
    # FORWARD
    # ─────────────────────────────────────────────────────────────────────────

    def forward(self, entrada: list) -> list[float]:
        if len(entrada) < self.n_entradas:
            entrada = entrada + [0.0] * (self.n_entradas - len(entrada))

        tensor = torch.tensor(entrada[:self.n_entradas], dtype=torch.float32)

        # Sequência de curto prazo (transformer)
        if self.ultimo_estado_oculto is None:
            sequencia = tensor.unsqueeze(0).unsqueeze(0)
            self.ultimo_estado_oculto = tensor.clone()
        else:
            estado_anterior = self.ultimo_estado_oculto.unsqueeze(0).unsqueeze(0)
            atual = tensor.unsqueeze(0).unsqueeze(0)
            sequencia = torch.cat([estado_anterior, atual], dim=1)
            if sequencia.shape[1] > 10:
                sequencia = sequencia[:, -10:, :]
            self.ultimo_estado_oculto = tensor.clone()

        # Embedding + Transformer (curto prazo)
        x_curto = self.embedding(sequencia)
        for bloco in self.transformer:
            x_curto = bloco(x_curto)
        x_curto = x_curto.mean(dim=1)  # [1, 256]

        # LSTM para longo prazo
        self.memoria_longa.append(x_curto.detach().squeeze(0))

        if len(self.memoria_longa) >= 10:
            estados_recentes = list(self.memoria_longa)[-200:]
            seq_longa = torch.stack(estados_recentes, dim=0).unsqueeze(0)

            if self.lstm_hidden is None:
                lstm_out, self.lstm_hidden = self.lstm(seq_longa)
            else:
                h, c = self.lstm_hidden
                h = h.detach()
                c = c.detach()
                lstm_out, self.lstm_hidden = self.lstm(seq_longa, (h, c))

            x_longo = self.proj_lstm(lstm_out[:, -1, :])
        else:
            x_longo = x_curto

        # Cross-attention
        x_curto_3d = x_curto.unsqueeze(1) if x_curto.dim() == 2 else x_curto
        x_longo_3d = x_longo.unsqueeze(1) if x_longo.dim() == 2 else x_longo

        x_cross, _ = self.cross_attention(x_curto_3d, x_longo_3d, x_longo_3d)
        x_cross = x_cross.squeeze(1)

        # Combina tudo
        x_combinado = x_curto + x_longo * 0.3 + x_cross * 0.2
        x_combinado = x_combinado + self.residual_1(x_combinado) * 0.3

        self.estado_interno = 0.9 * self.estado_interno + 0.1 * x_combinado.detach()
        self.ultima_entrada = x_combinado.clone()

        # Cada horizonte usa combinação diferente + embedding único
        saidas = []
        xs_cabecas = []
        for i, cab in enumerate(self.cabecas):
            if i < 4:
                x = x_curto * 0.7 + x_cross * 0.2 + x_longo * 0.1
            elif i < 7:
                x_base = x_curto * 0.4 + x_cross * 0.3 + x_longo * 0.3
                if i == 4:
                    x = x_base + x_curto * 0.15
                elif i == 5:
                    x = x_base + x_longo * 0.15
                else:
                    x = x_base + x_longo * 0.3
            elif i < 9:
                x_base = x_longo * 0.6 + x_cross * 0.3 + x_curto * 0.1
                if i == 7:
                    x = x_base + x_curto * 0.1
                else:
                    x = x_base + x_longo * 0.2
            else:
                x = x_longo * 0.8 + x_cross * 0.2

            emb = self.horizon_embeddings[i] * 3.0
            x = torch.cat([x, emb], dim=1)   # [1, 256+32]
            x = self.proj_embed(x)            # [1, 256]
            x = x + self.residual_1(x) * 0.3

            xs_cabecas.append(x.detach())
            saidas.append(float(cab(x).item()))

        self._ultimos_x_cabecas = xs_cabecas
        return saidas

    # ─────────────────────────────────────────────────────────────────────────
    # APRENDER
    # ─────────────────────────────────────────────────────────────────────────

    def aprender(self, recompensas):
        if self.ultima_entrada is None:
            return

        if isinstance(recompensas, (int, float)):
            recompensas = [float(recompensas)] * N_HORIZONTES
        elif isinstance(recompensas, torch.Tensor):
            if recompensas.numel() == 0:
                return
            recompensas = recompensas.detach().flatten().tolist()
        elif not isinstance(recompensas, list):
            return

        if len(recompensas) != N_HORIZONTES:
            if len(recompensas) == 1:
                recompensas = [recompensas[0]] * N_HORIZONTES
            else:
                return

        if any(math.isnan(r) or math.isinf(r) for r in recompensas):
            return

        self.otimizador.zero_grad()

        x = self.ultima_entrada
        if self._ultimos_x_cabecas is None:
            return

        preds = torch.cat([cab(x_i) for cab, x_i in zip(self.cabecas, self._ultimos_x_cabecas)], dim=1)
        confianca = self.cabeca_confianca(x)
        volatilidade = self.cabeca_volatilidade(x)

        alvo = torch.tensor([recompensas], dtype=torch.float32)

        if preds.shape != alvo.shape:
            return

        loss_mse = F.mse_loss(preds, alvo)
        loss_mae = F.l1_loss(preds, alvo)
        loss_huber = F.smooth_l1_loss(preds, alvo)

        erro_absoluto = torch.abs(preds - alvo).mean()
        target_confianca = torch.sigmoid(1 - erro_absoluto).view_as(confianca)
        loss_confianca = F.binary_cross_entropy(confianca, target_confianca)

        loss_volatilidade = volatilidade.mean()

        if N_HORIZONTES > 1:
            loss_consistencia = torch.mean((preds[:, 1:] - preds[:, :-1]) ** 2)

            pesos_temporais = torch.tensor(
                [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0], dtype=torch.float32
            )
            preds_ponderadas = preds[:, :-1] * pesos_temporais.unsqueeze(0)
            loss_estrutura = torch.abs(preds_ponderadas.mean() - preds[:, -1]).mean() * 0.1
        else:
            loss_consistencia = torch.tensor(0.0)
            loss_estrutura = torch.tensor(0.0)

        # FIX: usa list() para iterar sobre os parâmetros corretamente
        loss_reg = sum(
            torch.sum(p ** 2) for cab in list(self.cabecas)[-3:] for p in cab.parameters()
        ) * 1e-5

        loss = (loss_huber * 0.4 +
                loss_mse * 0.15 +
                loss_mae * 0.1 +
                loss_confianca * 0.1 +
                loss_consistencia * 0.1 +
                loss_estrutura * 0.05 +
                loss_volatilidade * 0.05 +
                loss_reg * 0.05)

        loss.backward()

        grad_norm = torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=0.3)
        self.memoria_gradientes.append(grad_norm.item())

        self.otimizador.step()

        if self.geracao < self.warmup_steps:
            lr = 1e-4 + (1e-3 - 1e-4) * (self.geracao / self.warmup_steps)
            for pg in self.otimizador.param_groups:
                pg['lr'] = lr
        else:
            self.scheduler.step()

        self.memoria_loss.append(loss.item())
        self.memoria_erros.append(erro_absoluto.item())

        with torch.no_grad():
            preds_np = preds[0].detach().tolist()
            conf = confianca.item()

            for i, (pred, real) in enumerate(zip(preds_np, recompensas)):
                if i < 4:
                    peso_base = min(1.0, max(0.1, conf * 2))
                elif i < 7:
                    peso_base = min(1.0, max(0.1, conf * 1.5))
                elif i < 9:
                    peso_base = min(1.0, max(0.1, conf * 1.2))
                else:
                    peso_base = min(1.0, max(0.1, conf * 1.0))

                if (pred > 0) == (real > 0):
                    self.n_acertos[i] += peso_base
                else:
                    self.n_erros[i] += (1 - peso_base * 0.5)

        self.geracao += 1

    # ─────────────────────────────────────────────────────────────────────────
    # PERSISTÊNCIA
    # ─────────────────────────────────────────────────────────────────────────

    def salvar_com_nome(self, caminho_completo: str):
        os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
        torch.save({
            'model_state_dict': self.state_dict(),
            'optimizer_state_dict': self.otimizador.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'n_acertos': self.n_acertos,
            'n_erros': self.n_erros,
            'geracao': self.geracao,
            'historico_loss': list(self.memoria_loss),
            'memoria_erros': list(self.memoria_erros),
            'estado_interno': self.estado_interno,
            'versao': 'v2_bugfix'
        }, caminho_completo)

    def carregar(self, caminho: str = "data/mentes_pytorch") -> bool:
        arquivo = f"{caminho}/mente_{self.id_agente}.pt"
        if os.path.exists(arquivo):
            try:
                ck = torch.load(arquivo, map_location='cpu')
                self.load_state_dict(ck['model_state_dict'], strict=False)
                self.otimizador.load_state_dict(ck['optimizer_state_dict'])

                if 'scheduler_state_dict' in ck:
                    try:
                        self.scheduler.load_state_dict(ck['scheduler_state_dict'])
                    except Exception:
                        pass

                self.n_acertos = ck.get('n_acertos', [0] * N_HORIZONTES)
                self.n_erros = ck.get('n_erros', [0] * N_HORIZONTES)
                self.geracao = ck.get('geracao', 0)
                self.memoria_loss = deque(ck.get('historico_loss', []), maxlen=100)
                self.memoria_erros = deque(ck.get('memoria_erros', []), maxlen=50)

                if 'estado_interno' in ck:
                    self.estado_interno = ck['estado_interno']

                print(f"[PyTorch] Mente {self.id_agente} carregada (estabilidade: {self.learning_stability})")
                return True
            except Exception as e:
                print(f"[PyTorch] Erro ao carregar mente {self.id_agente}: {e}")
        return False

    def para_dict(self) -> dict:
        return {
            "id_agente": self.id_agente,
            "n_acertos": self.n_acertos,
            "n_erros": self.n_erros,
            "geracao": self.geracao,
            "accuracy_por_horizonte": self.accuracy_por_horizonte,
            "confidence": self.confidence,
            "learning_stability": self.learning_stability,
            "tipo": "pytorch_v2_bugfix"
        }