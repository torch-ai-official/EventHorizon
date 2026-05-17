# mind.py
# ─────────────────────────────────────────────────────────────────────────────
# A Mente é a IA persistente. Sobrevive ao reset do Universo.
# Cada agente tem uma Mente identificada pelo seu ID.
# Futuramente pode ser substituída por um modelo PyTorch.
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import math
import random


CAMINHO_MENTE = "data/minds.json"


class MenteAgente:
    """
    Rede neural linear simples de um agente.
    Aprende via SGD online (reforço).
    Pode ser substituída por um modelo PyTorch no futuro.
    """

    N_ENTRADAS = 5  # energia, energia_outro, distancia, delta_global, score_memoria

    def __init__(self, id_agente: int):
        
        self.id_agente  = id_agente
        self.pesos      = [random.uniform(-1, 1) for _ in range(self.N_ENTRADAS)]
        self.bias       = random.uniform(-0.5, 0.5)
        self.taxa       = 0.01

        # Rastreamento
        self.ultima_entrada: list | None = None
        self.ultima_acao: float = 0.0
        self.n_acertos  = 0
        self.n_erros    = 0
        self.geracao    = 0   # incrementa a cada vez que o corpo morre/reseta

    # ── Inferência ────────────────────────────────────────────────────────────
    def forward(self, entrada: list) -> float:
        # Garante tamanho correto
        while len(self.pesos) < len(entrada):
            self.pesos.append(random.uniform(-1, 1))

        soma = sum(e * w for e, w in zip(entrada, self.pesos)) + self.bias
        saida = math.tanh(soma)

        self.ultima_entrada = entrada
        self.ultima_acao    = saida
        return saida

    # ── Aprendizado ───────────────────────────────────────────────────────────
    def aprender(self, recompensa: float):
        if self.ultima_entrada is None:
            return

        for i in range(len(self.pesos)):
            self.pesos[i] += self.taxa * recompensa * self.ultima_entrada[i]

        self.bias += self.taxa * recompensa

        if recompensa > 0:
            self.n_acertos += 1
        else:
            self.n_erros += 1

    # ── Serialização ──────────────────────────────────────────────────────────
    def para_dict(self) -> dict:
        return {
            "id_agente":  self.id_agente,
            "pesos":      self.pesos,
            "bias":       self.bias,
            "taxa":       self.taxa,
            "n_acertos":  self.n_acertos,
            "n_erros":    self.n_erros,
            "geracao":    self.geracao,
        }

    @staticmethod
    def de_dict(d: dict) -> "MenteAgente":
        m = MenteAgente(d["id_agente"])
        m.pesos     = d.get("pesos",     m.pesos)
        m.bias      = d.get("bias",      m.bias)
        m.taxa      = d.get("taxa",      m.taxa)
        m.n_acertos = d.get("n_acertos", 0)
        m.n_erros   = d.get("n_erros",   0)
        m.geracao   = d.get("geracao",   0)
        return m

    @property
    def accuracy(self) -> float:
        total = self.n_acertos + self.n_erros
        return self.n_acertos / total if total > 0 else 0.5


class BancoMentes:
    """
    Gerencia todas as mentes persistentes.
    Salva em data/minds.json independente do universe.json.
    """

    def __init__(self, caminho: str = CAMINHO_MENTE):
        self.caminho = caminho             
        self.mentes = {}
        self.ultimo_id_global = 0
        self.carregar()

    # ── Acesso ────────────────────────────────────────────────────────────────
    def obter(self, id_agente: int) -> MenteAgente:
        """Retorna a mente do agente, criando uma nova se não existir."""
        if id_agente not in self.mentes:
            self.mentes[id_agente] = MenteAgente(id_agente)
        return self.mentes[id_agente]

    def notificar_morte(self, id_agente: int):
        """
        Quando um corpo morre, a mente sobrevive mas registra a geração.
        Os pesos são mantidos — o aprendizado não se perde.
        """
        if id_agente in self.mentes:
            self.mentes[id_agente].geracao += 1

    def resetar_mente(self, id_agente: int):
        """
        Reset explícito de uma mente específica (raro — só se necessário).
        """
        self.mentes[id_agente] = MenteAgente(id_agente)

    def resetar_todas(self):
        """Apaga todas as mentes. Use com cuidado."""
        self.mentes = {}
        self.salvar()

    # ── Persistência ──────────────────────────────────────────────────────────
    def salvar(self):
        os.makedirs("data", exist_ok=True)

        temp = self.caminho + ".tmp"

        with open(temp, "w") as f:
            json.dump({
                "ultimo_id_global": self.ultimo_id_global,
                "mentes": {
                    str(id_): m.para_dict()
                    for id_, m in self.mentes.items()
                }
            }, f, indent=2)

        os.replace(temp, self.caminho)

    def carregar(self):
        if not os.path.exists(self.caminho):
            return

        try:
            with open(self.caminho, "r") as f:
                dados = json.load(f)

            self.ultimo_id_global = dados.get("ultimo_id_global", 0)

            self.mentes = {
                int(id_): MenteAgente.de_dict(m)
                for id_, m in dados.get("mentes", {}).items()
            }

            print(f"[Mente] {len(self.mentes)} mentes carregadas.")

        except Exception as e:
            print(f"[Mente] Erro ao carregar mentes: {e}")
            self.mentes = {}

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        if not self.mentes:
            return {"total": 0}
        accs = [m.accuracy for m in self.mentes.values()]
        return {
            "total":        len(self.mentes),
            "accuracy_avg": round(sum(accs) / len(accs), 3),
            "accuracy_max": round(max(accs), 3),
            "accuracy_min": round(min(accs), 3),
            "geracoes_max": max(m.geracao for m in self.mentes.values()),
        }
    
    def gerar_novo_id(self):
        """Retorna um ID que nunca conflita com mentes existentes."""
        self.ultimo_id_global += 1
        self.salvar()  # Salva imediatamente para garantir persistência
        return self.ultimo_id_global
    
       

    def limpar_mentes_orfas(self, ids_ativos):
        """
        Remove mentes cujos IDs não estão mais em uso.
        
        Args:
            ids_ativos: Lista ou set de IDs ativos no universo.
        """
        ids_ativos_set = set(ids_ativos)
        orfas = [id_ for id_ in self.mentes.keys() if id_ not in ids_ativos_set]
        
        for id_ in orfas:
            # Opcional: salvar em um arquivo de "mentes mortas" antes de remover
            self._arquivar_mente_morta(id_)
            del self.mentes[id_]
        
        if orfas:
            print(f"[Mente] {len(orfas)} mentes órfãs removidas: {orfas[:10]}...")
            self.salvar()
        
        return len(orfas)

    def _arquivar_mente_morta(self, id_agente):
        """Salva mente morta para análise futura (opcional)."""
        if id_agente not in self.mentes:
            return
        
        arquivo_mortas = "data/minds_mortas.json"
        try:
            if os.path.exists(arquivo_mortas):
                with open(arquivo_mortas, "r") as f:
                    mortas = json.load(f)
            else:
                mortas = []
            
            mortas.append({
                "id": id_agente,
                "mente": self.mentes[id_agente].para_dict(),
                "timestamp": __import__("time").time()
            })
            
            # Mantém apenas as últimas 1000
            mortas = mortas[-1000:]
            
            with open(arquivo_mortas, "w") as f:
                json.dump(mortas, f, indent=2)
        except Exception as e:
            print(f"[Mente] Erro ao arquivar mente {id_agente}: {e}")

    def sincronizar_id_maximo(self, id_max_universo):
        """
        Garante que o contador de IDs do banco de mentes está pelo menos
        no valor máximo do universo.
        """
        if id_max_universo > self.ultimo_id_global:
            self.ultimo_id_global = id_max_universo
            self.salvar()
            print(f"[Mente] ID máximo sincronizado para {self.ultimo_id_global}")

        
   

    def get_max_id(self):
        """Retorna o maior ID de mente existente."""
        return max(self.mentes.keys()) if self.mentes else 0