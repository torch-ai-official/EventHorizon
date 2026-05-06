# engine.py
import json #persistência
import os
import random
import time
import uuid
import math
import statistics

def gerar_dado_anelado(raio_nucleo=6, raio_interno=12, raio_externo=18):
    pixels = []

  

    # ========= ANEL INTERNO (bem cheio, energético) =========
    for _ in range(420):
        ang = random.random() * 2 * math.pi
        r = random.uniform(raio_interno - 1.8, raio_interno + 1.8)

        jitter = random.uniform(-0.4, 0.4)
        x = math.cos(ang) * (r + jitter)
        y = math.sin(ang) * (r + jitter)

        brilho = random.uniform(0.75, 0.95)
        pixels.append((x, y, brilho))

    # ========= ANEL EXTERNO (difuso / instável) =========
    for _ in range(260):
        ang = random.random() * 2 * math.pi
        r = random.uniform(raio_externo - 3.0, raio_externo + 3.0)

        jitter = random.uniform(-0.6, 0.6)
        x = math.cos(ang) * (r + jitter)
        y = math.sin(ang) * (r + jitter)

        brilho = random.uniform(0.4, 0.65)
        pixels.append((x, y, brilho))

    return pixels

def consumo_por_tick(dado):
        base = 0.000002
        dinamico = 0.0000005 * dado["energia"]
        fase, tensao, coerencia = dado["estado"]
        fator_estado = 1 + 0.3 * tensao + 0.2 * (1 - coerencia) + 0.1 * abs(math.sin(fase))
        return (base + dinamico) * fator_estado

def eficiencia(dado):
        consumo = consumo_por_tick(dado)
        if consumo <= 0:
            return float("inf")
        return dado["energia"] / consumo

def perda_universo(dado, outro, energia):
    perda_dado = consumo_por_tick(dado)
    perda_outro = consumo_por_tick(outro)

    dissipacao_pulso = energia * 0.02
    ganho_sincronizacao = 0
    perda_total = (
        perda_dado + 
        perda_outro + 
        dissipacao_pulso - 
        ganho_sincronizacao
    )

    return perda_total

def custo_futuro(dado):
        horizonte = 10 + dado["energia"] * 5
        consumo = consumo_por_tick(dado)
        return consumo * horizonte 

       
class Universo:
    def __init__(self, caminho="data/universe.json"):
        self.caminho = caminho
        self.caminho_mortos = "data/dados_mortos.json"
        self.dados = []
        self.apps = []
        self.dados_mortos = []
        self.mortes_pendentes = 0
        self.simulation_time = 0.0
        self.start_real_time = time.time()
        self.stats_history = []
        self.stats_interval = 1.0
        self._last_stats_time = time.time()
        self.ultimo_id = 0  # guarda o último ID usado
        self.pulsos = []
        self.clusters = {}
        self.historico_pulsos = []
        self.resultados_terminal = []
        self.memoria_global = {
            "energia_total": 0.0,
            "energia_anterior": 0.0,
            "delta_energia": 0.0,
            "entropia": 0.0
        }
        self.carregar()
        self.carregar_mortos()

    
    def delta_sobrevivencia(self, dado, outro, energia, pos="None"):
        custo_antes = (custo_futuro(dado) + custo_futuro(outro))
        dado_virtual = dado["energia"] - energia
        outro_virtual = outro["energia"] + energia
        if dado_virtual <= 0:
            return -float("inf")
        
        custo_depois = (
        custo_futuro({**dado, "energia": dado_virtual}) +
        custo_futuro({**outro, "energia": outro_virtual})
        )

        dissipacao = energia * 0.02
        return custo_antes - custo_depois - dissipacao
    
    def atualizar_consciencia_global(self):
        energia_atual = self.energia_total()

        self.memoria_global["energia_anterior"] = self.memoria_global["energia_total"]
        self.memoria_global["energia_total"] = energia_atual
        self.memoria_global["delta_energia"] = (
            energia_atual - self.memoria_global["energia_anterior"]
        )

        # entropia simples: dispersão de energia
        if self.dados:
            medias = energia_atual / len(self.dados)
            variancia = sum(
                (d["energia"] - medias) ** 2 for d in self.dados
            ) / len(self.dados)
            self.memoria_global["entropia"] = variancia
    
    def criar_dado(self, tipo="padrão", pos=None, config=None):
        config = config or {}
        self.ultimo_id += 1

        # ===== Energia inicial variada por tipo =====
        energia_base = 8
        if tipo == "padrão":
            energia = energia_base + random.uniform(-2, 2)
        elif tipo == "energetico":
            energia = energia_base + random.uniform(3, 6)
        elif tipo == "fraco":
            energia = energia_base + random.uniform(-5, -1)

        # ===== Fator de tempo inicial diferente =====
        fator_tempo = random.uniform(0.8, 1.2)

        # ===== Estado inicial com diversidade =====
        fase = random.uniform(0, 2 * math.pi)
        tensao = random.uniform(0, 0.1)
        coerencia = random.uniform(0.4, 0.8)

        energia = config.get("energy", energia)
        fator_tempo = config.get("time_factor", fator_tempo)

        fase = config.get("phase", fase)
        tensao = config.get("tension", tensao)
        coerencia = config.get("coherence", coerencia) 



        # ===== Posição inicial =====
        if pos is None:

            cluster_centro = [
                random.randint(200, 400),
                random.randint(150, 350)
            ]

            if random.random() < 0.3:
                pos = [
                    cluster_centro[0] + random.randint(-30, 30),
                    cluster_centro[1] + random.randint(-30, 30)
                ]
            else:
                pos = [
                    random.randint(10, 1280),
                    random.randint(10, 720)
                ]

        else:
            pos = [float(pos[0]), float(pos[1])]

        dado = {
            "id": self.ultimo_id,
            "pos": pos,
            "energia": energia,
            "tempo_proprio": 0,
            "fator_tempo": fator_tempo,
            "memoria": [],
            "cooldown": 0.0,
            "pixels": gerar_dado_anelado(raio_nucleo=6, raio_interno=12, raio_externo=18),
            "dado_t": random.uniform(0, 1000),
            "bits": [1, 1, 1],
            "estado": [fase, tensao, coerencia],
            "previsao": 0.0,
            "rede": {
                "pesos": [random.uniform(-1, 1) for _ in range(4)],
                "bias": random.uniform(-0.5, 0.5),
                "taxa": 0.01
                },
            "ultima_entrada": None,
            "ultima_energia": energia,
            "ultima_acao": 0.0,
            "dna": {
                "agressiveness": config.get("agressiveness", random.uniform(0, 1)),
                "cooperation": config.get("cooperation", random.uniform(0, 1)),
                "exploration": config.get("exploration", random.uniform(0, 1))
            }
                
        }

        

       
        self.dados.append(dado)
        self.salvar()
        return dado
    
    
    
    def forward(self, dado, energia_outro, distancia):

        memoria_score = self.score_memoria(dado)

        entrada = [
            dado["energia"],
            energia_outro,
            distancia / 200,
            self.memoria_global["delta_energia"],
            memoria_score   # 🔥 NOVO
        ]

        pesos = dado["rede"]["pesos"]
        bias = dado["rede"]["bias"]

        # 🔥 ajuste: garantir mesmo tamanho
        while len(pesos) < len(entrada):
            pesos.append(random.uniform(-1, 1))

        soma = sum(e * w for e, w in zip(entrada, pesos)) + bias

        saida = math.tanh(soma)

        dado["ultima_entrada"] = entrada
        dado["ultima_acao"] = saida

        return saida
            
    def pode_transferir(self, origem, destino, energia):
        
        b0, b1, b2 = origem["bits"]

        if b0 == 0:
            return False
        if b1 == 0:
            return False
        if b2 == 0 and origem["energia"] - energia < 2.0:
            return False

       

        if origem["energia"] - energia <= 0:
            return False
        
        return True
        

    

    def salvar(self):
        os.makedirs("data", exist_ok=True)

        temp_path = self.caminho + ".tmp"

        with open(temp_path, "w") as f:
            json.dump({"ultimo_id": self.ultimo_id, "dados": self.dados}, f, indent=4)

        os.replace(temp_path, self.caminho)  # substituição segura



    def carregar(self):
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, "r") as f:
                    universo_salvo = json.load(f)

                self.dados = universo_salvo.get("dados", [])
                self.ultimo_id = universo_salvo.get("ultimo_id", 0)

            except Exception as e:
                print("[ERRO] Falha ao carregar universo:", e)

                # backup automático
                os.rename(self.caminho, self.caminho + ".corrompido")

                self.dados = []
                self.ultimo_id = 0

    def salvar_mortos(self):
        os.makedirs("data", exist_ok=True)
        with open(self.caminho_mortos, "w") as f:
            json.dump(self.dados_mortos, f, indent=4)

    def carregar_mortos(self):
        if os.path.exists(self.caminho_mortos):
            with open(self.caminho_mortos, "r") as f:
                self.dados_mortos = json.load(f)

    def enviar_pulso(self, id_origem, id_destino, energia=0.2, resultado_terminal=None):
        origem = next((d for d in self.dados if d["id"] == id_origem), None)
        destino = next((d for d in self.dados if d["id"] == id_destino), None)

        if self.existe_pulso(id_origem, id_destino):
            return False

        if origem is None or destino is None:
            return False

        if origem["energia"] < energia:
            return False
 

        if "memoria" not in origem:
            origem["memoria"] = []

        if resultado_terminal is not None:
            velocidade = 1.5
            destino_viavel = self.escolher_destino_viavel(origem, velocidade)
            if destino_viavel is None:
                return False
            destino = destino_viavel


        

        pulso_id = str(uuid.uuid4())

        origem["memoria"].append({
            "acao": "enviou pulso",
            "destino": destino["id"],
            "energia": energia,
            "pulso_id": pulso_id
        })

        origem["energia"] -= energia


        

        dx = destino["pos"][0] - origem["pos"][0]
        dy = destino["pos"][1] - origem["pos"][1]
        distancia = (dx*dx + dy*dy) ** 0.5

        pulso = {
            "id": pulso_id,
           "origem": id_origem,
           "destino": id_destino,
           "energia": energia,
           "progresso": 0.0,
           "pos_origem": origem["pos"][:],
           "pos_destino": destino["pos"][:],
           "pos": origem["pos"][:],
           "distancia": max(distancia, 1),
           "velocidade": 1.5,
           "resultado_terminal": resultado_terminal,
           "expressao": None
        }



        self.pulsos.append(pulso)

        self.historico_pulsos.append({
            "origem": id_origem,
            "destino": id_destino,
            "energia": energia,
            "tempo": self.simulation_time
        })

        if len (self.historico_pulsos) > 300:
            self.historico_pulsos.pop(0)
        return True
    
    
    def aprender(self, dado, recompensa):

        if dado["ultima_entrada"] is None:
            return

        taxa = dado["rede"]["taxa"]

        for i in range(len(dado["rede"]["pesos"])):
            dado["rede"]["pesos"][i] += taxa * recompensa * dado["ultima_entrada"][i]

        dado["rede"]["bias"] += taxa * recompensa


    def evoluir_pulsos(self, escala):
        for pulso in self.pulsos[:]:
            origem = next((d for d in self.dados if d["id"] == pulso["origem"]), None)
            destino = next(
                    (d for d in self.dados if d["id"] == pulso["destino"]),
                    None
                )
            
            if origem is None:
                self.pulsos.remove(pulso)
                continue

            if destino is None:
                self.pulsos.remove(pulso)
                continue

            c = 2.0
            velocidade = min(pulso["velocidade"], c)
        
            # ===== AVANÇA NO TEMPO =====
            if pulso["distancia"] > 0:
                delta = (velocidade * escala * origem["fator_tempo"]) / pulso["distancia"]
                pulso["progresso"] += delta

            # ===== CHEGOU AO DESTINO =====
            if pulso["progresso"] >= 1.0:

                # 🔥 NOVO: se for pulso externo, registrar resultado
                if pulso.get("expressao"):
                    try:
                        resultado = eval(pulso["expressao"])
                        texto = f"{pulso['expressao']} = {resultado}"
                        self.resultados_terminal.append(texto)

                    except:
                        self.resultados_terminal.append("Error computing expression")

                elif pulso.get("resultado_terminal"):
                    self.resultados_terminal.append(pulso["resultado_terminal"])
                

                impacto = pulso["energia"] - consumo_por_tick(destino)
                impacto_global = impacto + 0.2 * self.memoria_global["delta_energia"]
                self.aprender(origem, impacto_global)


                if destino:
                    destino["energia"] += pulso["energia"]

                    perturbacao = pulso["energia"] * 0.05
                    destino["estado"][0] += perturbacao
                    destino["estado"][1] += pulso["energia"]

                    impacto = pulso["energia"] - consumo_por_tick(destino)

                    origem = next(d for d in self.dados if d["id"] == pulso["origem"])

                    impacto_global = impacto + self.memoria_global["delta_energia"]

                    origem["memoria"].append({
                        "tipo": "feedback",
                        "impacto_local": impacto,
                        "impacto_global": impacto_global
                    })

                self.pulsos.remove(pulso)
                continue  # próximo pulso

            # ===== MOVIMENTO ESPACIAL (SE AINDA ESTIVER VIAJANDO) =====

            ox, oy = pulso["pos_origem"]
            dx, dy = pulso["pos_destino"]

            pulso["distancia"] = ((dx - ox)**2 + (dy - oy)**2)**0.5
            pulso["velocidade"] = 1
            pulso["energia"] *= 0.999

            t = pulso["progresso"]
            pulso["pos"][0] = ox + (dx - ox) * t
            pulso["pos"][1] = oy + (dy - oy) * t
   
    def energia_dados(self):
        return sum(d["energia"] for d in self.dados)
    def energia_pulsos(self):
        return sum(p["energia"] for p in self.pulsos)
    def energia_total(self):
        return self.energia_dados() + self.energia_pulsos()
    
    def status_universo(self):
        return {
            "dados": len(self.dados),
            "pulsos": len(self.pulsos),
            "energia_total": self.energia_total()
        }
    
    def listar_pulsos(self):
        return [
           {
            "origem": p["origem"],
            "destino": p["destino"],
            "energia": p["energia"]
           }
           for p in self.pulsos
        ]
    
    
    def aplicar_consumo(self, dado, escala):
        consumo = consumo_por_tick(dado)
        dado["energia"] -= consumo * escala * dado["fator_tempo"]
        dado["energia"] = max(0, dado["energia"])

        dado["energia"] = max(0, dado["energia"])

    def aplicar_relatividade(self, dado, escala):
        energia = dado["energia"]
        fase, tensao, coerencia = dado["estado"]
        dado["fator_tempo"] = 1 / (1 + 0.1 * energia * (1 + 0.5 * (1 - coerencia)) + 0.05 * abs(math.sin(fase)))
        dado["tempo_proprio"] += escala * dado["fator_tempo"]

    def calcular_acao_global(self):
        energia = self.energia_total()
        entropia = self.memoria_global["entropia"]
        variacao = self.memoria_global["delta_energia"]
        fluxo = self.fluxo_total()
        alpha = 0.05
        beta = 0.5
        gamma = 0.2
        kappa = -0.05


        S = alpha * energia + beta * entropia + gamma * variacao + kappa * fluxo
        return S
    
    def calcular_acao_local(self, dado):
        energia = dado["energia"]
        entropia = abs(dado["energia"] - statistics.mean(d["energia"] for d in self.dados))
        variacao = self.memoria_global["delta_energia"]
        fluxo = self.fluxo_total()

        entradas = [energia, entropia, variacao, fluxo]

        pesos = dado["rede"]["pesos"]

        while len(pesos) < len(entradas):
            pesos.append(random.uniform(-1, 1))
            S = sum(e * w for e, w in zip(entradas, pesos))

        return S

    def decidir_interacoes(self, dado):

        dna = dado.get("dna", {})

        agressividade = dna.get("agressiveness", 0.5)
        cooperacao = dna.get("cooperation", 0.5)

        if dado["energia"] < 0.5:
            return

        for outro in self.dados:

            if outro is dado:
                continue

            dx = dado["pos"][0] - outro["pos"][0]
            dy = dado["pos"][1] - outro["pos"][1]
            distancia = (dx*dx + dy*dy) ** 0.5

            if distancia > 120:
                continue

            sync = self.sincronizacao(dado, outro)

            if sync < 0.2:
                continue

            # 🔥 DECISÃO AGORA É NEURAL
            dna = dado.get("dna", {})

            aggressiveness = dna.get("aggressiveness", 0.5)
            cooperation = dna.get("cooperation", 0.5)
            exploration = dna.get("exploration", 0.5)

            saida = self.forward(dado, outro["energia"], distancia)
            memoria_score = self.score_memoria(dado)

            # 🔥 DNA influencia decisão
            saida_final = (
                saida
                + 0.5 * memoria_score
                + 0.4 * aggressiveness
                + 0.3 * cooperation * self.sincronizacao(dado, outro)
            )
            # se a rede decidir não enviar
            if saida_final <= 0:
                continue

            base_envio = saida_final * 0.5

            fator_dna = 0.5 + aggressiveness * 0.7 + cooperation * sync

            energia = min(dado["energia"] * fator_dna, base_envio)

            if energia <= 0:
                continue

            # garante que não envia mais do que tem
            energia = min(energia, dado["energia"])

            self.enviar_pulso(dado["id"], outro["id"], energia)

            clusters = self.detectar_clusters()

            for cluster in clusters:

                energia_cluster = sum(d["energia"] for d in cluster)

                if energia_cluster > 30:

                    for d in cluster:
                        d["estado"][1] += 0.01

            # opcional: enviar para apenas um por tick
            break


    def matar_dado(self, dado):
        dado["_morrer"] = True

    def processar_mortes(self):
        if not self.dados:
            return

        novos_dados = []
        for dado in self.dados:
            if dado.get("_morrer"):
                self.dados_mortos.append({
                    "id": dado["id"],
                    "estado": dado["estado"],
                    "tempo_vida": dado["tempo_proprio"]
                })

            # libera memória pesada
                dado["pixels"] = None
                dado["memoria"] = None
            else:
                novos_dados.append(dado)

        self.dados = novos_dados

    def finalizar(self):
        self.salvar()
        self.salvar_mortos()
        

    def existe_pulso(self, origem, destino):
        return any(
            p["origem"] == origem and p["destino"] == destino for p in self.pulsos
        )
    
    def atualizar_bits(self, dado):

        ritmo = dado["fator_tempo"]

        # BIT 0 → ritmo lento (alta dilatação)
        dado["bits"][0] = 1 if ritmo < 0.5 else 0

        # BIT 1 → ritmo médio
        dado["bits"][1] = 1 if 0.5 <= ritmo < 0.8 else 0

        # BIT 2 → ritmo rápido
        dado["bits"][2] = 1 if ritmo >= 0.8 else 0

    def obter_telemetria(self):
        tamanho_kb = 0
        if os.path.exists(self.caminho):
            tamanho_kb = os.path.getsize(self.caminho) / 1024

        return {
            "name": os.path.basename(self.caminho),
            "size": f"{tamanho_kb:.2f} KB",
            "living_units": len(self.dados),
            "dead_units": len(self.dados_mortos),
            "total_energy": self.energia_total()
        }
    
    def atualizar_estado(self, dado, escala):
        fase, tensao, coerencia = dado["estado"]

        # fase evolui com tempo próprio
        fase += escala * dado["fator_tempo"]

        # tensão depende de energia
        tensao += 0.001 * dado["energia"]

        # coerência decai levemente
        coerencia *= 0.999

        dado["estado"] = [fase, tensao, coerencia]
    
    def sobrevivera_ate(self, dado, tempo):
        consumo = consumo_por_tick(dado)
        energia_futura = dado["energia"] - consumo * tempo
        return energia_futura > 0
    
    def tempo_de_viagem(self, origem, destino, velocidade):
        dx = destino["pos"][0] - origem["pos"][0]
        dy = destino["pos"][1] - origem["pos"][1]
        distancia = (dx**2 + dy**2)**0.5
        return distancia / max(velocidade, 0.0001)
    def escolher_destino_viavel(self, origem, velocidade):
        candidatos = []
        for dado in self.dados:
            if dado["id"] == origem["id"]:
                continue
            tempo = self.tempo_de_viagem(origem, dado, velocidade)
            if self.sobrevivera_ate(dado, tempo):
                candidatos.append((tempo, dado))
        if not candidatos:
            return None
        candidatos.sort(key=lambda x: x[0])
        return candidatos[0][1]
    
    def sincronizacao(self, d1, d2):
        fase1, tensao1, coerencia1 = d1["estado"]
        fase2, tensao2, coerencia2 = d2["estado"]

        diff = abs(fase1 - fase2)

        if diff > math.pi:
            diff = 2 * math.pi - diff

        alinhamento = 1 - (diff / math.pi)
        estabilidade = (coerencia1 + coerencia2) / 2
        return alinhamento * estabilidade

    def fluxo_total(self):
        return sum(abs(p["energia"]) for p in self.pulsos)

    def detectar_loops_energia(self):
        loops = []

        for p1 in self.historico_pulsos:
            for p2 in self.historico_pulsos:
                if p1["destino"] == p2["origem"]:
                    for p3 in self.historico_pulsos:
                        if p2["destino"] == p3["origem"] and p3["destino"] == p1["origem"]:
                            loop = (p1["origem"], p2["origem"], p3["origem"])
                            if loop not in loops:
                                loops.append(loop)
        return loops
    
    def detectar_clusters(self):

        clusters = []
        visitados = set()

        for d in self.dados:

            if d["id"] in visitados:
                continue

            grupo = [d]

            for outro in self.dados:

                if outro is d:
                    continue

                dx = d["pos"][0] - outro["pos"][0]
                dy = d["pos"][1] - outro["pos"][1]

                dist = (dx*dx + dy*dy)**0.5

                if dist < 80:
                    grupo.append(outro)

            if len(grupo) > 3:

                for g in grupo:
                    visitados.add(g["id"])

                clusters.append(grupo)

        return clusters
        
    def estabilizar_loops(self):

        loops = self.detectar_loops_energia()

        for loop in loops:

            chave = tuple(sorted(loop))

            if chave not in self.clusters:
                self.clusters[chave] = 0

            self.clusters[chave] += 1

            # quando um loop aparece várias vezes
            if self.clusters[chave] > 10:

                for dado in self.dados:

                    if dado["id"] in loop:

                        dado["estado"][2] = min(
                            1.0,
                            dado["estado"][2] + 0.01
                        )    

    def ler_solucao(self):

        clusters = self.detectar_clusters()

        if not clusters:
            return None

        maior = max(clusters, key=lambda c: sum(d["energia"] for d in c))

        energia = sum(d["energia"] for d in maior)

        coerencia = statistics.mean(d["estado"][2] for d in maior)

        return {
            "tamanho": len(maior),
            "energia": energia,
            "coerencia": coerencia
        }


    def collect_stats(self):

        if not self.dados:
            return

        energia_total = sum(d["energia"] for d in self.dados)
        num_dados = len(self.dados)

        tempos = [d["tempo_proprio"] for d in self.dados]

        media_tau = statistics.mean(tempos)
        desvio_tau = statistics.pstdev(tempos) if len(tempos) > 1 else 0

        registro = {
            "simulation_time": self.simulation_time,
            "energia_total": energia_total,
            "num_dados": num_dados,
            "media_tau": media_tau,
            "desvio_tau": desvio_tau,
            "num_pulsos": len(self.pulsos),
        }

        self.stats_history.append(registro)
        ultimo = self.stats_history[-1]


    def medir_equilibrio(self):

        if len(self.dados) < 2:
            return None

        energias = [d["energia"] for d in self.dados]

        media = statistics.mean(energias)
        desvio = statistics.pstdev(energias)

        return {
            "media": media,
            "desvio": desvio,
            "min": min(energias),
            "max": max(energias)
        }
    
    def apps_ativos(self):

        for app in self.apps:

            if app.nome in ["flow_app", "balance_app", "crypto_app"]:
                if getattr(app, "ativo", False):
                    return True

        return False
    

    def score_memoria(self, dado):
        if not dado["memoria"]:
            return 0.0

        impactos = []

        for m in dado["memoria"]:
            if m.get("tipo") == "feedback":
                impacto = m.get("impacto_local", 0)
                impactos.append(impacto)

        if not impactos:
            return 0.0

        # média dos impactos
        media = sum(impactos) / len(impactos)

        # limitar para evitar explosões
        return max(-1.0, min(1.0, media))


    