# mind.py - VERSÃO CORRIGIDA (Arquivo Principal)

import json
import os
import time
from collections import deque

# ⭐ Importa a implementação correta baseada na configuração
MODO_IA = os.getenv("MODO_IA", "pytorch")

if MODO_IA == "pytorch":
    
    CAMINHO_MENTE = "data/minds.json"
    from Software.core.mind_pytorch import MenteTorch as MenteAgente
    print("🤖 PyTorch ACTIVATED - Rede Neural Profunda")
    
else:
    CAMINHO_MENTE = "data/minds_linear.json"
    from Software.core.mind_linear import MenteAgenteLinear as MenteAgente
    print("📊 Modo Linear - IA Clássica")


# ⭐ BANCO DE MENTES (PERMANECE AQUI)
class BancoMentes:
    """
    Gerencia todas as mentes persistentes.
    Salva em data/minds.json independente do universe.json.
    """

    def __init__(self, caminho: str = None):
        self.caminho = caminho  or CAMINHO_MENTE           
        self.mentes = {}
        self.ultimo_id_global = 0
        self.carregar()

    def obter(self, id_agente: int):
        """Retorna a mente do agente, criando uma nova se não existir."""
        if id_agente not in self.mentes:
            self.mentes[id_agente] = MenteAgente(id_agente)
        return self.mentes[id_agente]

    def notificar_morte(self, id_agente: int):
        if id_agente in self.mentes:
            self.mentes[id_agente].geracao += 1

    def resetar_mente(self, id_agente: int):
        self.mentes[id_agente] = MenteAgente(id_agente)

    def resetar_todas(self):
        self.mentes = {}
        self.salvar()

    def salvar(self):
        os.makedirs("data", exist_ok=True)
        temp = self.caminho + ".tmp"
        
        # ⭐ IMPORTANTE: Verifica se a mente tem método para_dict
        mentes_dict = {}
        for id_, m in self.mentes.items():
            if hasattr(m, 'salvar'):
                try:
                    m.salvar()
                except Exception as e:
                    print(f"Erro ao salvar mente {id_}: {e}")
            if hasattr(m, 'para_dict'):
                mentes_dict[str(id_)] = m.para_dict()
            else:
                # PyTorch mind tem método diferente
                mentes_dict[str(id_)] = {
                    "id_agente": m.id_agente,
                    "n_acertos": m.n_acertos,
                    "n_erros": m.n_erros,
                    "geracao": m.geracao,
                    "tipo": "pytorch"
                }
        
        with open(temp, "w") as f:
            json.dump({
                "ultimo_id_global": self.ultimo_id_global,
                "mentes": mentes_dict
            }, f, indent=2)
        
        os.replace(temp, self.caminho)

    def carregar(self):
        if not os.path.exists(self.caminho):
            return

        try:
            with open(self.caminho, "r") as f:
                dados = json.load(f)

            self.ultimo_id_global = dados.get("ultimo_id_global", 0)
            
            self.mentes = {}
            for id_str, m_data in dados.get("mentes", {}).items():
                id_ = int(id_str)
                mente = MenteAgente(id_)
                
                # Carrega estatísticas básicas
                mente.n_acertos = m_data.get("n_acertos", 0)
                mente.n_erros = m_data.get("n_erros", 0)
                mente.geracao = m_data.get("geracao", 0)
                
                # Se for linear, carrega pesos
                if "pesos" in m_data:
                    mente.pesos = m_data["pesos"]
                    mente.bias = m_data.get("bias", 0)

                 
                # ⭐ CARREGA O MODELO PYTORCH
                if hasattr(mente, 'carregar'):
                    if mente.carregar():
                        print(f"[Mente] Modelo PyTorch {id_} carregado")
                    else:
                        print(f"[Mente] Modelo PyTorch {id_} não encontrado, criando novo")
                
                self.mentes[id_] = mente

            print(f"[Mente] {len(self.mentes)} mentes carregadas.")

        except Exception as e:
            print(f"[Mente] Erro ao carregar mentes: {e}")
            self.mentes = {}

    def stats(self) -> dict:
        if not self.mentes:
            return {"total": 0}
        accs = [m.accuracy for m in self.mentes.values()]
        return {
            "total": len(self.mentes),
            "accuracy_avg": round(sum(accs) / len(accs), 3),
            "accuracy_max": round(max(accs), 3),
            "accuracy_min": round(min(accs), 3),
            "geracoes_max": max(m.geracao for m in self.mentes.values()),
        }
    
    def gerar_novo_id(self):
        self.ultimo_id_global += 1
        self.salvar()
        return self.ultimo_id_global
    
    def limpar_mentes_orfas(self, ids_ativos):
        ids_ativos_set = set(ids_ativos)
        orfas = [id_ for id_ in self.mentes.keys() if id_ not in ids_ativos_set]
        
        for id_ in orfas:
            del self.mentes[id_]
        
        if orfas:
            print(f"[Mente] {len(orfas)} mentes órfãs removidas")
            self.salvar()
        
        return len(orfas)

    def get_max_id(self):
        return max(self.mentes.keys()) if self.mentes else 0