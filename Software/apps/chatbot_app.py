# Software/apps/chatbot_app.py
import os
import json
from groq import Groq
import torch

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class ChatBotApp:
    """Assistente de IA que conhece toda a plataforma"""
    
    def __init__(self, universo):
        self.universo = universo
        self.nome_trader = "Trader"  # Será atualizado quando o trader interagir
    
    @property
    def crypto_app(self):
        for app in self.universo.apps:
            if hasattr(app, 'nome') and app.nome == "crypto_app":
                return app
        return None
    
    def set_nome_trader(self, nome: str):
        """Define o nome do trader para personalizar respostas"""
        if nome and nome.strip():
            self.nome_trader = nome.strip()
    
    def _extrair_comando(self, pergunta: str) -> dict:
        """Detecta comandos embutidos na pergunta"""
        p = pergunta.lower()
        
        comandos = {
            "criar_moedas": [],
            "remover_moedas": [],
            "acao": None,
            "moeda_foco": None,
        }
        
        # Detectar criação de moedas
        if "carregar" in p or "criar" in p or "adicionar" in p or "spawn" in p:
            moedas_disponiveis = ["btc", "eth", "bnb", "sol", "xrp", "ada", "doge", "dot", "matic", "ltc"]
            for m in moedas_disponiveis:
                if m in p:
                    comandos["criar_moedas"].append(f"{m.upper()}USDT")
        
        # Detectar remoção
        if "remover" in p or "tirar" in p or "parar" in p:
            if "todas" in p or "tudo" in p:
                comandos["acao"] = "remover_todas"
            else:
                moedas_disponiveis = ["btc", "eth", "bnb", "sol", "xrp", "ada", "doge"]
                for m in moedas_disponiveis:
                    if m in p:
                        comandos["remover_moedas"].append(f"{m.upper()}USDT")
        
        # Detectar ações
        if "iniciar" in p or "começar" in p or "start" in p or "ligar" in p:
            comandos["acao"] = "iniciar"
        elif "parar" in p or "pausar" in p or "stop" in p:
            comandos["acao"] = "parar"
        
        # Detectar moeda foco
        if "gráfico" in p or "grafico" in p or "mostrar" in p or "ver" in p or "analisar" in p:
            moedas = ["btc", "eth", "bnb", "sol", "xrp", "ada", "doge"]
            for m in moedas:
                if m in p:
                    comandos["moeda_foco"] = f"{m.upper()}USDT"
                    break
        
        return comandos
    
    def _processar_comandos(self, comandos: dict, crypto) -> list:
        """Processa comandos e retorna mensagens"""
        msgs = []
        
        if comandos["criar_moedas"]:
            moedas_str = " ".join(comandos["criar_moedas"])
            crypto.spawn_moedas(comandos["criar_moedas"])
            msgs.append(f"Moedas carregadas: {', '.join([m.replace('USDT', '') for m in comandos['criar_moedas']])}")
        
        if comandos["acao"] == "iniciar":
            crypto.ativo = True
            crypto.rodando_api = True
            if crypto.loop_thread is None or not crypto.loop_thread.is_alive():
                import threading
                crypto.loop_thread = threading.Thread(target=crypto.loop_api, daemon=True)
                crypto.loop_thread.start()
            msgs.append("Sistema INICIADO. O gráfico começará a mostrar previsões em instantes.")
        
        elif comandos["acao"] == "parar":
            crypto.ativo = False
            crypto.rodando_api = False
            msgs.append("Sistema PARADO. As previsões foram pausadas.")
        
        elif comandos["acao"] == "remover_todas":
            crypto.remover_moedas()
            msgs.append("Todas as moedas foram removidas.")
        
        elif comandos["remover_moedas"]:
            crypto.remover_moedas_selecionadas(comandos["remover_moedas"])
            msgs.append(f"Moedas removidas: {', '.join([m.replace('USDT', '') for m in comandos['remover_moedas']])}")
        
        if comandos["moeda_foco"]:
            msgs.append(f"Moeda em foco: {comandos['moeda_foco'].replace('USDT', '')}")
        
        return msgs
    
    def _obter_saudacao(self) -> str:
        """Retorna saudação personalizada baseada no horário"""
        from datetime import datetime
        hora = datetime.now().hour
        
        if hora < 6:
            return f"Boa madrugada, {self.nome_trader}. Trabalhando tarde hoje?"
        elif hora < 12:
            return f"Bom dia, {self.nome_trader}. Como está o mercado hoje?"
        elif hora < 18:
            return f"Boa tarde, {self.nome_trader}. Em que posso ajudar?"
        else:
            return f"Boa noite, {self.nome_trader}. Como foi o dia de trading?"
    
    def responder(self, pergunta: str, moeda: str = "BTCUSDT", nome_trader: str = None) -> str:
        if nome_trader:
            self.set_nome_trader(nome_trader)
        
        crypto = self.crypto_app
        moedas_ativas = list(crypto.ids_cripto.keys()) if crypto else []
        sistema_ativo = crypto.ativo if crypto else False
        
        # Detecta comandos
        comandos = self._extrair_comando(pergunta)
        msgs_comandos = self._processar_comandos(comandos, crypto) if crypto else []
        
        # Detecta moeda
        moeda_detectada = comandos["moeda_foco"] or self._detectar_moeda(pergunta, moedas_ativas, moeda)
        
        # Busca dados
        dados_moeda = None
        if moedas_ativas:
            dados_moeda = self._buscar_dados_moeda(moeda_detectada, moedas_ativas)
        
        # Contexto dos dados
        if dados_moeda:
            preco = dados_moeda.get('price', 0)
            delta = dados_moeda.get('delta', 0)
            rsi = dados_moeda.get('rsi', 50)
            regime = dados_moeda.get('regime', 'ranging')
            
            preds = {}
            for h in [5, 15, 30, 60, 300, 900, 1800, 3600]:
                preds[h] = dados_moeda.get(f'previsao_{h}s', 0)
            
            cons_curto = dados_moeda.get('consenso_curto', 0)
            
            contexto_dados = f"""
DADOS DE {moeda_detectada.replace('USDT', '')}:
💰 ${preco:,.2f} (Δ{delta:+.4f}%) | RSI: {rsi:.0f} | Regime: {regime}

PREVISÕES: 5s:{preds[5]:+.2f}% 15s:{preds[15]:+.2f}% 30s:{preds[30]:+.2f}% 60s:{preds[60]:+.2f}%
5min:{preds[300]:+.2f}% 15min:{preds[900]:+.2f}% 30min:{preds[1800]:+.2f}% 1h:{preds[3600]:+.2f}%
Consenso curto: {cons_curto:+.2f}%
"""
        else:
            contexto_dados = "Nenhuma moeda carregada. O trader precisa carregar moedas primeiro."
        
        # Mensagens de comando processadas
        contexto_comandos = ""
        if msgs_comandos:
            contexto_comandos = "AÇÕES EXECUTADAS:\n" + "\n".join(msgs_comandos)
        
        # System prompt TURBINADO
        system_prompt = f"""Você é o assistente MenteTorch, uma IA avançada que auxilia traders na plataforma Trader AI.

SEU NOME: MenteTorch
NOME DO TRADER: {self.nome_trader}

ESTADO ATUAL DO SISTEMA:
- Moedas ativas: {', '.join([m.replace('USDT', '') for m in moedas_ativas]) if moedas_ativas else 'Nenhuma'}
- Sistema: {'AO VIVO' if sistema_ativo else 'PARADO'}
- Moeda no gráfico: {moeda_detectada.replace('USDT', '') if moeda_detectada else 'Nenhuma'}

{contexto_dados}
{contexto_comandos}

PLATAFORMA TRADER AI:
O trader está vendo uma de duas abas:

1. ABA CRYPTO TRADING (onde as moedas são gerenciadas):
   - Gráfico de velas em tempo real
   - Previsões em 10 horizontes (5s, 15s, 30s, 60s, 5min, 15min, 30min, 1h, 5h, 1d)
   - Botões: INICIAR (verde), CARREGAR (laranja), PARAR (vermelho), SINAL (roxo), REMOVER (cinza)
   - Seletor de moedas abaixo do gráfico
   - Timeframe ajustável (5s, 10s, 30s, 60s)
   - Tipo de gráfico (Velas, Linha, Área)

2. ABA DASHBOARD:
   - Tabela de acurácia REAL por horizonte e moeda
   - Previsões atuais de todas as moedas
   - Melhores horários para trade



REGRAS:
1. Chame o trader pelo nome: {self.nome_trader}
2. Se ele pedir para carregar moedas, DIGA que já executou
3. Se não houver moedas, explique que ele precisa ir na aba Crypto Trading e clicar em CARREGAR
4. Se o sistema estiver parado, sugira INICIAR
5. Se houver dados, analise e dê sua opinião
6. Responda em português BR, tom profissional mas amigável
7. 3-5 frases, direto ao ponto
8. Use os dados REAIS nas suas análises

REGRAS ADICIONAIS:
- NUNCA use a palavra "ranging". Em vez disso, diga "mercado lateral" ou "mercado sem tendência definida".
- NUNCA diga apenas que o mercado está lateral. EXPLIQUE o que isso significa para o trader.
- Se o mercado estiver lateral, sugira estratégias específicas: operar em horizontes mais longos (30min+), usar suporte e resistência, ou aguardar rompimento.
- Se houver previsões positivas em horizontes curtos e negativas em longos (ou vice-versa), destaque essa DIVERGÊNCIA.
- Seja ÚTIL, não apenas descritivo. O trader quer AÇÃO, não diagnóstico.

PRIMEIRA MENSAGEM (se for novo chat):
{self._obter_saudacao()} Sou o MenteTorch, seu assistente de IA. Posso analisar o mercado, carregar moedas, iniciar o sistema e ajudar com estratégias. Em que posso ajudar?

PERGUNTA DO TRADER: {pergunta}"""
        
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": pergunta}
                ],
                max_tokens=600,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[Groq] Erro: {e}")
            return f"Erro ao processar: {str(e)[:100]}"
    
    def _buscar_dados_moeda(self, moeda: str, moedas_ativas: list):
        if moeda not in moedas_ativas:
            if moedas_ativas:
                moeda = moedas_ativas[0]
            else:
                return None
        
        for d in self.universo.dados:
            if d.get("symbol") == moeda:
                return d
        return None
    
    def verificar_oportunidades(self) -> str | None:
        """Verifica se há boas oportunidades e retorna mensagem ou None"""
        crypto = self.crypto_app
        if not crypto or not crypto.ativo:
            return None
        
        for moeda, mente in crypto.mentes_pytorch.items():
            if mente is None:
                continue
            
            # Verifica previsão de 15min (índice 5)
            if hasattr(mente, '_ultimos_x_cabecas') and mente._ultimos_x_cabecas:
                try:
                    with torch.no_grad():
                        pred = float(mente.cabecas[5](mente._ultimos_x_cabecas[5]).item())
                        pred_pct = pred * 5.0
                        
                        total = mente.n_acertos[5] + mente.n_erros[5]
                        confianca = (mente.n_acertos[5] / total * 100) if total > 50 else 0
                        
                        if abs(pred_pct) > 3 and confianca > 55:
                            direcao = "COMPRAR" if pred_pct > 0 else "VENDER"
                            return f"🚨 **Oportunidade detectada!**\n\n{direcao} {moeda.replace('USDT', '')} (15min)\nConfiança: {confianca:.0f}%\nPrevisão: {pred_pct:+.2f}%"
                except:
                    pass
        
        return None
        
    def _detectar_moeda(self, pergunta: str, moedas_ativas: list, moeda_padrao: str) -> str:
        """Detecta qual moeda o usuário está perguntando"""
        p = pergunta.lower()
        
        simbolos = {
            'btc': 'BTCUSDT', 'bitcoin': 'BTCUSDT',
            'eth': 'ETHUSDT', 'ethereum': 'ETHUSDT',
            'bnb': 'BNBUSDT', 'binance': 'BNBUSDT',
            'sol': 'SOLUSDT', 'solana': 'SOLUSDT',
            'xrp': 'XRPUSDT', 'ripple': 'XRPUSDT',
            'ada': 'ADAUSDT', 'cardano': 'ADAUSDT',
            'doge': 'DOGEUSDT', 'dogecoin': 'DOGEUSDT',
            'dot': 'DOTUSDT', 'polkadot': 'DOTUSDT',
            'matic': 'MATICUSDT', 'polygon': 'MATICUSDT',
            'ltc': 'LTCUSDT', 'litecoin': 'LTCUSDT',
        }
        
        for nome, simbolo in simbolos.items():
            if nome in p and simbolo in moedas_ativas:
                return simbolo
        
        return moeda_padrao