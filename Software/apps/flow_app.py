class FlowApp:

    nome = "flow_app"

    def __init__(self, universo):

        self.universo = universo

        self.source = None
        self.target = None

        self.ativo = False
        self.raio_pulso = 220

        self.visitados = set()
        self.pais = {}
        self.abertos = []
        self.ativos = set()
        self.proximos = set()
        self.fila = []
        self.energia_anteriores = {}
        self.custo = {}

    def handle(self, comando):

        if comando.startswith("flow source"):

            self.source = int(comando.split()[2])
            return [f"Source set to {self.source}"]

        if comando.startswith("flow target"):

            self.target = int(comando.split()[2])
            return [f"Target set to {self.target}"]
        
        if comando.startswith("flow range"):
            try:
                valor =  float(comando.split()[2])
                self.raio_pulso = valor
                return [f"Pulse range set to {self.raio_pulso}"]
            except (ValueError, IndexError):
                return ["Invalid range value"]

        if comando == "flow start":

            self.energia_anteriores = {d["id"]: d["energia"] for d in self.universo.dados}
            self.custo = {self.source: 0}

            if self.source is None or self.target is None:
                return ["Source or target not defined"]

            self.visitados = {self.source}
            self.ativos = {self.source}
            self.proximos = set()
            self.pais = {}
            self.abertos = [self.source]
            self.fila = [(self.source, 0)]

            return ["Flow problem initialized"]

        if comando == "flow run":

            if self.source is None or self.target is None:
                return ["Source or target not defined"]
            

            self.ativo = True
            return ["Flow simulation running"]

        if comando == "flow result":

            caminho = []

            atual = self.target

            while atual in self.pais:
                caminho.append(atual)
                atual = self.pais[atual]

            caminho.append(self.source)
            caminho.reverse()

            # calcular hops
            hops = len(caminho) - 1

            # calcular distância total
            distancia_total = 0

            for i in range(len(caminho) - 1):

                d1 = next((d for d in self.universo.dados if d["id"] == caminho[i]), None)
                d2 = next((d for d in self.universo.dados if d["id"] == caminho[i+1]), None)

                if d1 is None or d2 is None:
                    return float("inf")

                dx = d1["pos"][0] - d2["pos"][0]
                dy = d1["pos"][1] - d2["pos"][1]

                dist = (dx**2 + dy**2) ** 0.5

                distancia_total += dist

            return [
                "FLOW RESULT",
                "",
                f"path: {' -> '.join(map(str, caminho))}",
                f"hops: {hops}",
                f"distance: {round(distancia_total,2)}"
            ]

        if comando == "flow stop":
            self.ativo = False
            return ["Flow simulation stopped"]

        return None
    
    def update(self):

        if not self.ativo:
            return

        dados = self.universo.dados

        # ===== PASSO 1: primeiro pulso do source =====

        if not self.pais:

            origem = next((d for d in dados if d["id"] == self.source), None)
            target = next((d for d in dados if d["id"] == self.target), None)

            melhor = None
            melhor_dist = float("inf")

            dist_atual = self.distancia_ate_target(self.source, target)

            for outro in dados:

                if outro["id"] == self.source:
                    continue

                dx = origem["pos"][0] - outro["pos"][0]
                dy = origem["pos"][1] - outro["pos"][1]

                dist = (dx**2 + dy**2) ** 0.5

                if dist > self.raio_pulso:
                    continue

                dist_target_outro = self.distancia_ate_target(outro["id"], target)

                if dist_target_outro >= dist_atual:
                    continue

                custo_novo = self.custo[self.source] + dist

                if outro["id"] not in self.custo or custo_novo < self.custo[outro["id"]]:

                    self.custo[outro["id"]] = custo_novo

                    score = custo_novo + dist_target_outro  # A*

                    if score < melhor_dist:
                        melhor_dist = score
                        melhor = outro

            if melhor:

                self.universo.enviar_pulso(
                    self.source,
                    melhor["id"],
                    0.1
                )

                self.pais[melhor["id"]] = self.source

            return

        # ===== PASSO 2: detectar quem recebeu energia =====

        novos_ativos = []

        for d in dados:

            energia_anterior = self.energia_anteriores.get(d["id"], d["energia"])

            if d["energia"] > energia_anterior + 0.05:

                if d["id"] not in self.visitados:

                    novos_ativos.append(d["id"])
                    self.visitados.add(d["id"])

        # atualizar histórico
        for d in dados:
            self.energia_anteriores[d["id"]] = d["energia"]

        target = next((d for d in dados if d["id"] == self.target), None)

        # ===== PASSO 3: propagação =====

        for atual_id in novos_ativos:

            self.visitados.add(atual_id)

            atual = next(x for x in dados if x["id"] == atual_id)

            melhor = None
            melhor_dist = float("inf")

            dist_atual = self.distancia_ate_target(atual_id, target)

            for outro in dados:

                if outro["id"] in self.visitados:
                    continue

                dx = atual["pos"][0] - outro["pos"][0]
                dy = atual["pos"][1] - outro["pos"][1]

                dist = (dx**2 + dy**2) ** 0.5

                if dist > self.raio_pulso:
                    continue

                dist_target_outro = self.distancia_ate_target(outro["id"], target)

                if dist_target_outro >= dist_atual:
                    continue

                custo_novo = self.custo.get(atual_id, float("inf")) + dist

                if outro["id"] not in self.custo or custo_novo < self.custo[outro["id"]]:

                    self.custo[outro["id"]] = custo_novo

                    score = custo_novo + dist_target_outro  # A*

                    if score < melhor_dist:
                        melhor_dist = score
                        melhor = outro

            if melhor:

                self.universo.enviar_pulso(
                    atual_id,
                    melhor["id"],
                    0.1
                )

                self.pais[melhor["id"]] = atual_id

                if melhor["id"] == self.target:

                    self.ativo = False

                    texto = "[FLOW] path found"
                    self.universo.resultados_terminal.append(texto)

                    return
            
    def distancia_ate_target(self, id_dado, target):

        if target is None:
            return float("inf")

        dado = next((d for d in self.universo.dados if d["id"] == id_dado), None)

        if dado is None:
            return float("inf")

        dx = dado["pos"][0] - target["pos"][0]
        dy = dado["pos"][1] - target["pos"][1]

        return (dx**2 + dy**2) ** 0.5