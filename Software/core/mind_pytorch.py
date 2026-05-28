# Software/core/mind_pytorch.py - VERSÃO INSANA 💀🔥

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import math
from collections import deque

HORIZONTES = [5, 15, 30, 60]
N_HORIZONTES = len(HORIZONTES)

class AtencaoMultiCabeca(nn.Module):
    """⭐ ATENÇÃO - O segredo do Transformer! ⭐"""
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
    """⭐ BLOCO TRANSFORMER - O que o GPT usa! ⭐"""
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
    """💀 ARQUITETURA INSANA - TRANSFORMER + RESIDUAL + ATENÇÃO 💀"""
    
    def __init__(self, id_agente: int, n_entradas: int = 14):
        super().__init__()
        self.id_agente = id_agente
        self.n_entradas = n_entradas
        
        # ⚡ EMBEDDING - Projeta entrada para espaço de alta dimensão
        self.embedding = nn.Sequential(
            nn.Linear(n_entradas, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 256),
            nn.LayerNorm(256),
            nn.GELU(),
        )
        
        # 🧠 TRANSFORMER (como o GPT, mas menor)
        self.transformer = nn.ModuleList([
            BlocoTransformer(256, num_cabecas=8, dropout=0.1)
            for _ in range(4)  # 4 camadas de transformer
        ])
        
        # 🔄 CAMINHOS RESIDUAIS (aprendizado profundo)
        self.residual_1 = nn.Linear(256, 256)
        self.residual_2 = nn.Linear(256, 128)
        
        # 🎯 CABEÇAS COM ATENÇÃO CRUZADA
        self.cabecas = nn.ModuleList([
            nn.Sequential(
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
            ) for _ in HORIZONTES
        ])
        
        # 📊 CABEÇA DE CONFIANÇA (aprende quando está certa)
        self.cabeca_confianca = nn.Sequential(
            nn.Linear(256, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
        # 🔮 CABEÇA DE VOLATILIDADE (aprende a incerteza do mercado)
        self.cabeca_volatilidade = nn.Sequential(
            nn.Linear(256, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Softplus()  # Garante valores positivos
        )
        
        # ⚙️ OTIMIZADOR COM ADAPTABILIDADE
        self.otimizador = torch.optim.AdamW(
            self.parameters(),
            lr=0.001,
            betas=(0.9, 0.999),
            weight_decay=0.01,
            amsgrad=True
        )
        
        # 🔄 SCHEDULER COM WARMUP
        self.warmup_steps = 100
        self.scheduler = torch.optim.lr_scheduler.OneCycleLR(
            self.otimizador,
            max_lr=0.002,
            total_steps=10000,
            pct_start=0.1,
            anneal_strategy='cos'
        )
        
        # 📈 MEMÓRIA DE APRENDIZADO
        self.n_acertos = [0] * N_HORIZONTES
        self.n_erros = [0] * N_HORIZONTES
        self.geracao = 0
        
        # 🧠 MEMÓRIA DE ERROS (aprendizado contínuo)
        self.memoria_erros = deque(maxlen=50)
        self.memoria_loss = deque(maxlen=100)
        self.memoria_gradientes = deque(maxlen=20)
        
        self.ultima_entrada = None
        self.ultimo_estado_oculto = None
        
        # 🔥 ESTADO INTERNO (para aprendizado sequencial)
        self.estado_interno = torch.zeros(1, 256)
        
        print(f"[PyTorch] 🔥 Mente {id_agente} INSANA carregada (Transformer + Atenção + 4 cabeças)")
    
    def forward(self, entrada: list) -> list[float]:
        # Padroniza entrada
        if len(entrada) < self.n_entradas:
            entrada = entrada + [0.0] * (self.n_entradas - len(entrada))
        
        tensor = torch.tensor(entrada[:self.n_entradas], dtype=torch.float32)
        
        # Adiciona dimensão de sequência (passado + presente)
        if self.ultimo_estado_oculto is None:
            sequencia = tensor.unsqueeze(0).unsqueeze(0)
            self.ultimo_estado_oculto = tensor.clone()
        else:
            # Mantém uma janela de 5 estados anteriores
            estado_anterior = self.ultimo_estado_oculto.unsqueeze(0).unsqueeze(0)
            atual = tensor.unsqueeze(0).unsqueeze(0)
            sequencia = torch.cat([estado_anterior, atual], dim=1)
            if sequencia.shape[1] > 5:
                sequencia = sequencia[:, -5:, :]
            self.ultimo_estado_oculto = tensor.clone()
        
        # Embedding
        x = self.embedding(sequencia)
        
        # Transformer
        for bloco in self.transformer:
            x = bloco(x)
        
        # Pooling da sequência
        x = x.mean(dim=1)
        
        # Atualiza estado interno (memória de longo prazo)
        self.estado_interno = 0.9 * self.estado_interno + 0.1 * x.detach()
        
        # Caminhos residuais
        x = x + self.residual_1(x) * 0.3
        self.ultima_entrada = x.clone()
        
        # Gera previsões
        saidas = [float(cab(x).item()) for cab in self.cabecas]
        
        return saidas
    
    def aprender(self, recompensas):
        """Aprende com as recompensas - VERSÃO CORRIGIDA"""
        
        # ⭐ VERIFICAÇÃO 1: Entrada existe
        if self.ultima_entrada is None:
            return
        
        # ⭐ VERIFICAÇÃO 2: Normaliza o tipo da entrada
        if isinstance(recompensas, (int, float)):
            # Se for um número, repete para todos os horizontes
            recompensas = [float(recompensas)] * N_HORIZONTES
        elif isinstance(recompensas, torch.Tensor):
            # Se for tensor, converte para lista
            if recompensas.numel() == 0:
                print(f"[AVISO] Tensor vazio, ignorando")
                return
            recompensas = recompensas.detach().flatten().tolist()
        elif not isinstance(recompensas, list):
            print(f"[AVISO] Tipo não suportado: {type(recompensas)}")
            return
        
        # ⭐ VERIFICAÇÃO 3: Tamanho correto
        if len(recompensas) != N_HORIZONTES:
            # Se veio com 1 elemento, repete (fallback)
            if len(recompensas) == 1:
                recompensas = [recompensas[0]] * N_HORIZONTES
                print(f"[AVISO] Expandindo recompensa única para {N_HORIZONTES} horizontes")
            else:
                print(f"[AVISO] Tamanho incorreto: esperado {N_HORIZONTES}, recebido {len(recompensas)}")
                return
        
        # ⭐ VERIFICAÇÃO 4: Valores válidos
        if any(math.isnan(r) or math.isinf(r) for r in recompensas):
            print(f"[AVISO] Valores inválidos nas recompensas, ignorando")
            return
        
        self.otimizador.zero_grad()
        
        # Forward
        x = self.ultima_entrada
        
        # Previsões
        preds = torch.cat([cab(x) for cab in self.cabecas], dim=1)
        confianca = self.cabeca_confianca(x)
        volatilidade = self.cabeca_volatilidade(x)
        
        # ⭐ Targets com dimensão correta (1, N_HORIZONTES)
        alvo = torch.tensor([recompensas], dtype=torch.float32)
        
        # ⭐ VERIFICAÇÃO 5: Dimensões compatíveis
        if preds.shape != alvo.shape:
            print(f"[AVISO] Shape mismatch: preds {preds.shape}, alvo {alvo.shape}")
            return
        
        # 🔥 LOSS HÍBRIDO (aprendizado robusto)
        loss_mse = F.mse_loss(preds, alvo)
        loss_mae = F.l1_loss(preds, alvo)
        loss_huber = F.smooth_l1_loss(preds, alvo)
        
        # ⚡ LOSS DE CONFIANÇA (aprende quando não sabe)
        erro_absoluto = torch.abs(preds - alvo).mean()

        # ⭐ CORREÇÃO: Garante mesmo shape
        target_confianca = torch.sigmoid(1 - erro_absoluto).view_as(confianca)
        loss_confianca = F.binary_cross_entropy(confianca, target_confianca)
        
        # 📊 LOSS DE VOLATILIDADE (adapta ao mercado)
        loss_volatilidade = volatilidade.mean()
        
        # 🎯 LOSS DE CONSISTÊNCIA (previsões devem ser suaves)
        if N_HORIZONTES > 1:
            loss_consistencia = torch.mean((preds[:, 1:] - preds[:, :-1]) ** 2)
        else:
            loss_consistencia = torch.tensor(0.0)
        
        # 🔥 LOSS TOTAL (multi-objetivo)
        loss = (loss_huber * 0.5 + 
                loss_mse * 0.2 + 
                loss_mae * 0.1 + 
                loss_confianca * 0.1 + 
                loss_consistencia * 0.05 +
                loss_volatilidade * 0.05)
        
        loss.backward()
        
        # 🔥 GRADIENT CLIPPING ADAPTATIVO
        grad_norm = torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=0.5)
        self.memoria_gradientes.append(grad_norm.item())
        
        self.otimizador.step()
        
        # Scheduler com warmup
        if self.geracao < self.warmup_steps:
            # Warmup: learning rate cresce linearmente
            lr = 0.0001 + (0.001 - 0.0001) * (self.geracao / self.warmup_steps)
            for param_group in self.otimizador.param_groups:
                param_group['lr'] = lr
        else:
            self.scheduler.step()
        
        self.memoria_loss.append(loss.item())
        self.memoria_erros.append(erro_absoluto.item())
        
        # Atualiza acertos/erros com ponderação por confiança
        with torch.no_grad():
            preds_np = preds[0].detach().tolist()
            conf = confianca.item()
            
            for i, (pred, real) in enumerate(zip(preds_np, recompensas)):
                # Confiança adaptativa
                peso = min(1.0, max(0.1, conf * 2))
                
                if (pred > 0) == (real > 0):
                    self.n_acertos[i] += peso
                else:
                    self.n_erros[i] += (1 - peso * 0.5)
        
        self.geracao += 1
    
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
    def accuracy(self) -> float:
        accs = []
        for a, e in zip(self.n_acertos, self.n_erros):
            total = a + e
            accs.append(a / total if total > 0 else 0.5)
        return sum(accs) / len(accs) if accs else 0.5
    
    @property
    def accuracy_por_horizonte(self) -> list[float]:
        result = []
        for a, e in zip(self.n_acertos, self.n_erros):
            total = a + e
            result.append(round(a / total, 3) if total > 0 else 0.5)
        return result
    
    @property
    def loss_medio(self) -> float:
        if not self.memoria_loss:
            return 0.5
        return sum(self.memoria_loss) / len(self.memoria_loss)
    
    def salvar(self, caminho: str = "data/mentes_pytorch"):
        os.makedirs(caminho, exist_ok=True)
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
            'versao': 'insana_v2'
        }, f"{caminho}/mente_{self.id_agente}.pt")
    
    def carregar(self, caminho: str = "data/mentes_pytorch"):
        arquivo = f"{caminho}/mente_{self.id_agente}.pt"
        if os.path.exists(arquivo):
            try:
                ck = torch.load(arquivo, map_location='cpu')
                self.load_state_dict(ck['model_state_dict'], strict=False)
                self.otimizador.load_state_dict(ck['optimizer_state_dict'])
                
                if 'scheduler_state_dict' in ck:
                    self.scheduler.load_state_dict(ck['scheduler_state_dict'])
                
                self.n_acertos = ck.get('n_acertos', [0] * N_HORIZONTES)
                self.n_erros = ck.get('n_erros', [0] * N_HORIZONTES)
                self.geracao = ck.get('geracao', 0)
                self.memoria_loss = deque(ck.get('historico_loss', []), maxlen=100)
                self.memoria_erros = deque(ck.get('memoria_erros', []), maxlen=50)
                
                if 'estado_interno' in ck:
                    self.estado_interno = ck['estado_interno']
                
                print(f"[PyTorch] 🔥 Mente {self.id_agente} carregada (estabilidade: {self.learning_stability})")
                return True
            except Exception as e:
                print(f"[PyTorch] Erro ao carregar: {e}")
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
            "tipo": "pytorch_insana"
        }