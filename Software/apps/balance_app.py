class BalanceApp:
    nome = "balance_app"

    def __init__(self, universo):
        self.universo = universo
        self.ativo = False
        self.equilibrio_detectado = False
        self.interacoes = 0
        self.solucao_detectada = False
        self.loop_detectado = False

        self.config = {
            "units": None,
            "resource": None,
            "goal": None
        }


    def handle(self, comando):

        if comando.startswith("balance units"):
            valor = comando.split(" ", 2)[2]
            self.config["units"] = valor
            return [f"Units set to: {valor}"]

        if comando.startswith("balance resource"):
            valor = comando.split(" ", 2)[2]
            self.config["resource"] = valor
            return [f"Resource set to: {valor}"]

        if comando.startswith("balance goal"):
            valor = comando.split(" ", 2)[2]
            self.config["goal"] = valor
            return [f"Goal set to: {valor}"]
        
        if comando == "balance config":

            return [
                f"Units: {self.config['units']}",
                f"Resource: {self.config['resource']}",
                f"Goal: {self.config['goal']}"
            ]
        
        if comando == "balance start":
            if self.universo.dados < 2:
                return ["At least 2 units are required to start balance simulation"]

            self.equilibrio_detectado = False
            self.interacoes = 0
            self.ativo = False
            self.solucao_detectada = False
            self.loop_detectado = False

            if None in self.config.values():
                return ["Configuration incomplete"]

            import random

            for d in self.universo.dados:
                d["energia"] = random.uniform(1, 10)

            resultado = self.universo.medir_equilibrio()

            if resultado is None:
                return ["Error measuring balance"]

            return [
                "Problem initialized",
                f"Units = {self.config['units']}",
                f"Resource = {self.config['resource']}",
                f"Goal = {self.config['goal']}",
                f"Initial avg: {resultado['media']:.2f}",
                f"Initial dev: {resultado['desvio']:.2f}"
            ]
        
        if comando == "balance run":
           self.ativo = True
           return ["Balance simulation executed"]
        
        if comando == "balance result":

            energias = [d["energia"] for d in self.universo.dados]

            if not energias:
                return ["No units"]

            media = sum(energias) / len(energias)

            variancia = sum((e - media)**2 for e in energias) / len(energias)
            desvio = variancia ** 0.5

            return [
                "Balance Result",
                "",
                f"Units: {self.config['units']}",
                f"Resource: {self.config['resource']}",
                f"Goal: {self.config['goal']}",
                "",
                f"Average energy: {media:.2f}",
                f"Deviation: {desvio:.2f}",
                f"Min energy: {min(energias):.2f}",
                f"Max energy: {max(energias):.2f}"
                ]
        
        if comando == "balance stop":
            self.ativo = False
            return ["Balance simulation stopped"]
                
        return None
    
    def update(self):

        if not self.ativo:
            return

        dados = self.universo.dados

        if not dados:
            return

        media = sum(d["energia"] for d in dados) / len(dados)

        excesso = []
        deficit = []

        # separar quem tem sobra e quem precisa
        for d in dados:
            diff = d["energia"] - media

            if diff > 0.5:
                excesso.append((d, diff))

            elif diff < -0.5:
                deficit.append((d, -diff))

        # otimização: cada origem escolhe o melhor destino
        for origem, sobra in excesso:

            melhor_destino = None
            melhor_falta = 0
            melhor_custo = float("inf")

            for destino, falta in deficit:

                dx = origem["pos"][0] - destino["pos"][0]
                dy = origem["pos"][1] - destino["pos"][1]

                distancia = (dx**2 + dy**2) ** 0.5

                # custo combina distância e necessidade
                custo = distancia / (falta + 0.001)

                if custo < melhor_custo:
                    melhor_custo = custo
                    melhor_destino = destino
                    melhor_falta = falta

            if melhor_destino is None:
                continue

            energia = min(sobra, melhor_falta) * 0.2

            if energia <= 0:
                continue

            self.universo.enviar_pulso(
                origem["id"],
                melhor_destino["id"],
                energia
            )

            self.interacoes += 1

        resultado = self.universo.medir_equilibrio()

        if resultado:

            if resultado["desvio"] < 2.0 and not self.equilibrio_detectado:

                self.equilibrio_detectado = True
                self.ativo = False

                texto = (
                    f"[BALANCE] Stable configuration detected | "
                    f"avg={resultado['media']:.2f} "
                    f"dev={resultado['desvio']:.2f} "
                    f"| interactions={self.interacoes}"
                )

                self.universo.resultados_terminal.append(texto)

        # detectar solução emergente
        solucao = self.universo.ler_solucao()

        if solucao and not self.solucao_detectada:

            self.solucao_detectada = True

            texto = (
                f"[SOLUTION] cluster detected | "
                f"size={solucao['tamanho']} "
                f"energy={solucao['energia']:.2f} "
                f"coherence={solucao['coerencia']:.2f}"
            )

            self.universo.resultados_terminal.append(texto)

        # detectar loops de energia
        loops = self.universo.detectar_loops_energia()

        if loops and not self.loop_detectado:

            self.loop_detectado = True

            texto = f"[LOOP] energy cycle detected: {loops[0]}"

            self.universo.resultados_terminal.append(texto)