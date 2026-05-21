# mind_pytorch.py - Versão estável com PyTorch

import torch
import torch.nn as nn
import numpy as np
from collections import deque
import os

class MenteTorch(nn.Module):
    """
    Rede neural profunda com PyTorch.
    Mantém a mesma API do MenteAgente original para compatibilidade.
    """
    
    def __init__(self, id_agente: int, n_entradas: int = 12):
        super().__init__()
        self.id_agente = id_agente
        
        # Arquitetura simplificada (boa para começar)
        # 12 features → 32 neurônios → 16 → 1 saída
        self.rede = nn.Sequential(
            nn.Linear(n_entradas, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Tanh()  # Saída entre -1 e 1
        )
        
        # Otimizador com learning rate conservador
        self.otimizador = torch.optim.Adam(self.parameters(), lr=0.005)
        
        # Métricas (mesmas do MenteAgente)
        self.n_acertos = 0
        self.n_erros = 0
        self.geracao = 0
        
        # Cache para aprendizado
        self.ultima_entrada = None
        self.ultima_saida = 0.0
        self.historico_loss = deque(maxlen=100)
        
        print(f"[PyTorch] Mente {id_agente} criada com {n_entradas} entradas")
    
    def forward(self, entrada: list) -> float:
        """
        Inferência: recebe lista de features, retorna previsão (-1 a 1)
        """
        # Garante que a entrada tem o tamanho correto
        if len(entrada) < 12:
            # Se for menor, completa com zeros
            entrada = entrada + [0.0] * (12 - len(entrada))
        
        # Converte para tensor
        tensor = torch.tensor(entrada, dtype=torch.float32)
        self.ultima_entrada = tensor.clone()
        
        # Modo de avaliação (sem gradientes)
        with torch.no_grad():
            saida = self.rede(tensor)
            self.ultima_saida = float(saida.item())
        
        # Limita entre -1 e 1
        return max(-1.0, min(1.0, self.ultima_saida))
    
    def aprender(self, recompensa: float):
        """
        Aprendizado por reforço.
        Recompensa positiva → reforça ação, negativa → evita ação
        """
        if self.ultima_entrada is None:
            return
        
        # Converte recompensa para tensor alvo
        # Queremos que a saída se aproxime do sinal da recompensa
        alvo = torch.tensor([recompensa], dtype=torch.float32)
        
        # Forward com gradientes
        self.otimizador.zero_grad()
        saida = self.rede(self.ultima_entrada)
        
        # Loss = erro quadrático entre saída e recompensa
        loss = nn.MSELoss()(saida, alvo)
        
        # Backward
        loss.backward()
        self.otimizador.step()
        
        # Registra loss para monitoramento
        self.historico_loss.append(loss.item())
        
        # Atualiza estatísticas (igual ao MenteAgente)
        if recompensa > 0:
            self.n_acertos += 1
        else:
            self.n_erros += 1
    
    def salvar(self, caminho: str = "data/mentes_pytorch"):
        """Salva o modelo treinado"""
        os.makedirs(caminho, exist_ok=True)
        torch.save({
            'model_state_dict': self.state_dict(),
            'optimizer_state_dict': self.otimizador.state_dict(),
            'n_acertos': self.n_acertos,
            'n_erros': self.n_erros,
            'geracao': self.geracao,
            'historico_loss': list(self.historico_loss)
        }, f"{caminho}/mente_{self.id_agente}.pt")
        print(f"[PyTorch] Mente {self.id_agente} salva")
    
    def carregar(self, caminho: str = "data/mentes_pytorch"):
        """Carrega modelo salvo"""
        arquivo = f"{caminho}/mente_{self.id_agente}.pt"
        if os.path.exists(arquivo):
            try:
                checkpoint = torch.load(arquivo, map_location='cpu')
                self.load_state_dict(checkpoint['model_state_dict'])
                self.otimizador.load_state_dict(checkpoint['optimizer_state_dict'])
                self.n_acertos = checkpoint['n_acertos']
                self.n_erros = checkpoint['n_erros']
                self.geracao = checkpoint['geracao']
                self.historico_loss = deque(checkpoint['historico_loss'], maxlen=100)
                print(f"[PyTorch] Mente {self.id_agente} carregada (acertos: {self.n_acertos})")
                return True
            except Exception as e:
                print(f"[PyTorch] Erro ao carregar mente {self.id_agente}: {e}")
        return False
    
    @property
    def accuracy(self) -> float:
        """Acurácia (mesmo cálculo do MenteAgente)"""
        total = self.n_acertos + self.n_erros
        return self.n_acertos / total if total > 0 else 0.5
    
    @property
    def loss_medio(self) -> float:
        """Loss médio para monitoramento"""
        if not self.historico_loss:
            return 0.5
        return sum(self.historico_loss) / len(self.historico_loss)
    
    def para_dict(self) -> dict:
        return {
            "id_agente": self.id_agente,
            "n_acertos": self.n_acertos,
            "n_erros": self.n_erros,
            "geracao": self.geracao,
            "tipo": "pytorch"
        }