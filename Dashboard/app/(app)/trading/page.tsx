// app/trading/page.tsx — VERSÃO CORRIGIDA

"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import {
  Send, Bot, Loader2, Zap, TrendingUp, TrendingDown,
  Clock, BarChart3, Brain, Sparkles, Activity,
  Target, Shield, AlertTriangle, CheckCircle2,
  XCircle, RefreshCw, Star, ArrowUp, ArrowDown,
  DollarSign, Percent, Radio
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TradingChart } from "@/components/apps/TradingChart"
import { API_BASE_URL } from "@/lib/api"
import { useAlertas } from "@/contexts/AlertasContext"


// ============================================
// TIPOS (baseados no /dashboard/realtime)
// ============================================

interface MoedaRealtime {
  symbol: string
  price: number
  rsi: number
  regime: string
  geracoes: number
  acuracias_reais: Record<string, {
    acertos: number
    erros: number
    total: number
    acuracia: number
  }>
  previsoes: Record<string, number>
}

interface RealtimeData {
  moedas: MoedaRealtime[]
  total_moedas: number
  total_verificacoes: number
  melhor_moeda: MoedaRealtime | null
}

interface Message {
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

// ============================================
// COMPONENTE
// ============================================

export default function TradingPage() {
  // ── Estados ───────────────────────────────
  const [realtimeData, setRealtimeData] = useState<RealtimeData | null>(null)
  const [selectedSymbol, setSelectedSymbol] = useState("BTC")
  const [candles, setCandles] = useState<any[]>([])
  const [currentPrice, setCurrentPrice] = useState(0)
  const [previsoes, setPrevisoes] = useState<Record<string, number>>({})
  const [isRunning, setIsRunning] = useState(false)
  
  // ── Chat ───────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "💀☠️ **TRADER AI ASSISTANT**\n\nSou sua IA de trading proprietária com análise em 10 horizontes temporais. Pergunte sobre:\n\n• Sinais de entrada/saída\n• Análise técnica em tempo real\n• Performance das moedas\n• Melhores horários para operar\n• Previsões por horizonte",
      timestamp: new Date()
    }
  ])
  const [chatInput, setChatInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<HTMLInputElement>(null)

  // ============================================
  // FETCH: Dados em tempo real (a cada 3s)
  // ============================================
  
  const fetchRealtimeData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/dashboard/realtime`)
      const data: RealtimeData = await res.json()
      setRealtimeData(data)
      setIsRunning(data.total_moedas > 0)
    } catch (e) {
      console.error("Erro ao buscar dados:", e)
    }
  }, [])

  // ============================================
  // FETCH: Velas da moeda selecionada
  // ============================================
  
  const fetchCandles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/status`)
      const data = await res.json()
      const cryptoWithSymbol = data.dados?.find(
        (d: any) => d.symbol === `${selectedSymbol}USDT`
      )
      if (cryptoWithSymbol) {
        setCandles(cryptoWithSymbol.candles || [])
        setCurrentPrice(cryptoWithSymbol.price || 0)
        setPrevisoes({
          "5s": cryptoWithSymbol.previsao_5s || 0,
          "15s": cryptoWithSymbol.previsao_15s || 0,
          "30s": cryptoWithSymbol.previsao_30s || 0,
          "60s": cryptoWithSymbol.previsao_60s || 0,
          "5min": cryptoWithSymbol.previsao_300s || 0,
          "15min": cryptoWithSymbol.previsao_900s || 0,
          "30min": cryptoWithSymbol.previsao_1800s || 0,
          "1h": cryptoWithSymbol.previsao_3600s || 0,
          "5h": cryptoWithSymbol.previsao_18000s || 0,
          "1d": cryptoWithSymbol.previsao_86400s || 0,
        })
      }
    } catch (e) {
      // Silencioso
    }
  }, [selectedSymbol])

  // ============================================
  // EFFECTS
  // ============================================
  
  useEffect(() => {
    fetchRealtimeData()
    fetchCandles()
    
    const realtimeInterval = setInterval(fetchRealtimeData, 3000)
    const candlesInterval = setInterval(fetchCandles, 5000)
    
    return () => {
      clearInterval(realtimeInterval)
      clearInterval(candlesInterval)
    }
  }, [fetchRealtimeData, fetchCandles])

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // ============================================
  // CHAT: Enviar mensagem
  // ============================================
  
  async function sendChatMessage(content?: string) {
    const text = content || chatInput
    if (!text.trim() || chatLoading) return
    
    const userMsg: Message = {
      role: "user",
      content: text,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, userMsg])
    setChatInput("")
    setChatLoading(true)

    try {
      const res = await fetch(`${API_BASE_URL}/chatbot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pergunta: text,
          moeda: `${selectedSymbol}USDT`
        })
      })
      
      const data = await res.json()
      
      setMessages(prev => [...prev, {
        role: "assistant",
        content: data.resposta || "Desculpe, não consegui processar.",
        timestamp: new Date()
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "❌ Erro de conexão com o assistente.",
        timestamp: new Date()
      }])
    } finally {
      setChatLoading(false)
      chatInputRef.current?.focus()
    }
  }

  // ============================================
  // DADOS DERIVADOS (do /dashboard/realtime)
  // ============================================
  
  // Total de previsões = soma de todas as verificações
  const totalPrevisoes = realtimeData?.total_verificacoes || 0
  
  // Acurácia média geral (calculada dos dados)
  const acuraciaGeral = (() => {
    if (!realtimeData?.moedas?.length) return 0
    const todasAcuracias = realtimeData.moedas
      .flatMap(m => Object.values(m.acuracias_reais))
      .filter(a => a.total > 10)
    if (todasAcuracias.length === 0) return 0
    const soma = todasAcuracias.reduce((acc, a) => acc + a.acuracia, 0)
    return Math.round(soma / todasAcuracias.length)
  })()

  // Sinais ordenados por previsão (usando previsão de 15min)
  const sinaisOrdenados = (realtimeData?.moedas || [])
    .map(moeda => {
      const previsao15min = moeda.previsoes?.["15min"] || 0
      const acuracia15min = moeda.acuracias_reais?.["900"] // 900s = 15min
      
      return {
        symbol: moeda.symbol,
        previsao: previsao15min,
        confianca: acuracia15min?.acuracia || 50,
        acertos: acuracia15min?.acertos || 0,
        erros: acuracia15min?.erros || 0,
        total: acuracia15min?.total || 0,
      }
    })
    .filter(s => Math.abs(s.previsao) > 0.01) // Filtra sinais insignificantes
    .sort((a, b) => Math.abs(b.previsao) - Math.abs(a.previsao))

  // Moeda selecionada
  const selectedData = realtimeData?.moedas?.find(m => m.symbol === selectedSymbol)

  // ============================================
  // RENDER
  // ============================================
  
  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* ═══════════════════════════════════════ */}
      {/* COLUNA ESQUERDA (60%) */}
      {/* ═══════════════════════════════════════ */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-secondary/10">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600">
              <Radio className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold">Trading Ao Vivo</h1>
              <p className="text-[10px] text-muted-foreground">
                {totalPrevisoes.toLocaleString()} verificações • {acuraciaGeral}% acurácia geral
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {isRunning ? (
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                AO VIVO
              </span>
            ) : (
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-gray-500/20 text-gray-400 border border-gray-500/30">
                <div className="w-2 h-2 rounded-full bg-gray-400" />
                PARADO
              </span>
            )}
          </div>
        </div>

        {/* Área do gráfico */}
        <div className="flex-1 p-3 overflow-y-auto space-y-3">
          
          {/* Cards de top moedas */}
          <div className="grid grid-cols-4 gap-2">
            {(realtimeData?.moedas || []).slice(0, 4).map(coin => {
              const isSelected = coin.symbol === selectedSymbol
              const previsao15min = coin.previsoes?.["15min"] || 0
              
              return (
                <button
                  key={coin.symbol}
                  onClick={() => setSelectedSymbol(coin.symbol)}
                  className={cn(
                    "p-3 rounded-xl border text-left transition-all",
                    isSelected
                      ? "border-cyan-500/50 bg-cyan-500/10"
                      : "border-border/50 bg-secondary/20 hover:bg-secondary/30"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-bold">{coin.symbol}</span>
                    {previsao15min > 0 ? (
                      <ArrowUp className="w-3 h-3 text-green-400" />
                    ) : (
                      <ArrowDown className="w-3 h-3 text-red-400" />
                    )}
                  </div>
                  <p className="text-lg font-bold">${coin.price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                  <div className="flex items-center gap-1 mt-1">
                    <span className={cn("text-[10px]", previsao15min >= 0 ? "text-green-400" : "text-red-400")}>
                      {previsao15min > 0 ? "+" : ""}{previsao15min.toFixed(2)}%
                    </span>
                    <span className="text-[10px] text-muted-foreground">15min</span>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Gráfico principal */}
          <div className="rounded-xl border border-border/50 bg-secondary/10 p-2">
            {candles.length > 0 ? (
              <TradingChart
                candles={candles}
                currentPrice={currentPrice}
                prediction={previsoes["5s"] || 0}
                symbol={`${selectedSymbol}USDT`}
                isActive={isRunning}
                timeframe={5}
                chartType="candlestick"
                showIndicators={true}
                prediction5s={previsoes["5s"]}
                prediction15s={previsoes["15s"]}
                prediction30s={previsoes["30s"]}
                prediction60s={previsoes["60s"]}
                prediction300s={previsoes["5min"]}
                prediction900s={previsoes["15min"]}
                prediction1800s={previsoes["30min"]}
                prediction3600s={previsoes["1h"]}
                prediction18000s={previsoes["5h"]}
                prediction86400s={previsoes["1d"]}
              />
            ) : (
              <div className="h-80 flex items-center justify-center text-muted-foreground text-sm">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                Carregando gráfico...
              </div>
            )}
          </div>

          {/* Previsões 10 horizontes */}
          {selectedData && (
            <div className="rounded-xl border border-border/50 bg-secondary/10 p-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                Previsões — {selectedSymbol}
              </p>
              <div className="grid grid-cols-5 gap-1.5">
                {[
                  { time: "5s", value: previsoes["5s"] || 0 },
                  { time: "15s", value: previsoes["15s"] || 0 },
                  { time: "30s", value: previsoes["30s"] || 0 },
                  { time: "60s", value: previsoes["60s"] || 0 },
                  { time: "5min", value: previsoes["5min"] || 0 },
                  { time: "15min", value: previsoes["15min"] || 0 },
                  { time: "30min", value: previsoes["30min"] || 0 },
                  { time: "1h", value: previsoes["1h"] || 0 },
                  { time: "5h", value: previsoes["5h"] || 0 },
                  { time: "1d", value: previsoes["1d"] || 0 },
                ].map((pred, i) => {
                  const isPositive = pred.value >= 0
                  const precoAlvo = currentPrice * (1 + pred.value / 100)
                  
                  return (
                    <div
                      key={i}
                      className={cn(
                        "rounded-lg p-2 text-center border",
                        isPositive
                          ? "border-green-500/20 bg-green-500/5"
                          : "border-red-500/20 bg-red-500/5"
                      )}
                    >
                      <div className="text-[10px] text-muted-foreground">{pred.time}</div>
                      <div className={cn(
                        "text-xs font-bold font-mono",
                        isPositive ? "text-green-400" : "text-red-400"
                      )}>
                        {pred.value > 0 ? "+" : ""}{pred.value.toFixed(2)}%
                      </div>
                      <div className="text-[9px] text-muted-foreground">
                        ${precoAlvo.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Sinais atuais (do /dashboard/realtime) */}
          <div className="rounded-xl border border-border/50 bg-secondary/10 p-3">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-3">
              Sinais Ativos — Ordenados por Previsão (15min)
            </p>
            
            {sinaisOrdenados.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-muted-foreground border-b border-border/30">
                      <th className="text-left p-2 font-medium">Moeda</th>
                      <th className="text-right p-2">Sinal</th>
                      <th className="text-right p-2">Previsão</th>
                      <th className="text-right p-2">Confiança</th>
                      <th className="text-right p-2">Verificações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sinaisOrdenados.slice(0, 10).map(sinal => {
                      const direcao = sinal.previsao > 0.5 ? "COMPRAR" : sinal.previsao < -0.5 ? "VENDER" : "AGUARDAR"
                      const cor = direcao === "COMPRAR" ? "text-green-400" : direcao === "VENDER" ? "text-red-400" : "text-gray-400"
                      
                      return (
                        <tr key={sinal.symbol} className="border-b border-border/20 hover:bg-secondary/20">
                          <td className="p-2 font-medium">{sinal.symbol}</td>
                          <td className={cn("p-2 text-right font-bold", cor)}>{direcao}</td>
                          <td className={cn("p-2 text-right font-mono", sinal.previsao >= 0 ? "text-green-400" : "text-red-400")}>
                            {sinal.previsao > 0 ? "+" : ""}{sinal.previsao.toFixed(2)}%
                          </td>
                          <td className="p-2 text-right">{sinal.confianca}%</td>
                          <td className="p-2 text-right text-muted-foreground">{sinal.total}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Nenhum sinal disponível</p>
                <p className="text-xs mt-1">
                  {isRunning 
                    ? "Aguardando dados de verificação (10+ trades por horizonte)..." 
                    : "Inicie o sistema na aba Crypto Trading para gerar sinais."}
                </p>
              </div>
            )}
          </div>

        </div>
      </div>

      {/* ═══════════════════════════════════════ */}
      {/* COLUNA DIREITA (40%) — CHATBOT IA */}
      {/* ═══════════════════════════════════════ */}
      <div className="w-[400px] border-l border-border/50 flex flex-col bg-secondary/5">
        
        {/* Header do chat */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold">IA Assistant</p>
            <p className="text-[10px] text-muted-foreground">GROQ • 10 horizontes • Tempo real</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[10px] text-green-400">Online</span>
          </div>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
          {messages.map((msg, i) => (
            <div key={i} className={cn(
              "flex gap-2",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}>
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div className={cn(
                "max-w-[85%] rounded-2xl px-3 py-2",
                msg.role === "user"
                  ? "bg-cyan-500/20 border border-cyan-500/30"
                  : "bg-secondary/40 border border-border/30"
              )}>
                <div
                  className="text-xs whitespace-pre-wrap leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: msg.content
                      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-cyan-400">$1</strong>')
                      .replace(/• /g, '<span class="text-cyan-400">•</span> ')
                      .replace(/\n/g, '<br/>')
                  }}
                />
                <p className="text-[9px] text-muted-foreground mt-1">
                  {msg.timestamp.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}
          
          {chatLoading && (
            <div className="flex gap-2">
              <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                <Bot className="w-3.5 h-3.5 text-white" />
              </div>
              <div className="bg-secondary/40 border border-border/30 rounded-2xl px-3 py-2">
                <div className="flex gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" />
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "0.15s" }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce" style={{ animationDelay: "0.3s" }} />
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Sugestões */}
        {messages.length <= 1 && (
          <div className="px-3 pb-2">
            <p className="text-[9px] text-muted-foreground mb-1.5 uppercase tracking-wider">Sugestões</p>
            <div className="space-y-1">
              {[
                { icon: Zap, text: `Análise completa de ${selectedSymbol} agora`, cor: "text-yellow-400" },
                { icon: TrendingUp, text: "Qual moeda tem melhor acurácia em 15min?", cor: "text-green-400" },
                { icon: Target, text: "Melhor horário para operar hoje?", cor: "text-cyan-400" },
                { icon: Brain, text: "Como funciona a previsão de 10 horizontes?", cor: "text-purple-400" },
              ].map((sug, i) => (
                <button
                  key={i}
                  onClick={() => sendChatMessage(sug.text)}
                  className="flex items-center gap-2 w-full p-2 rounded-lg bg-secondary/20 border border-border/30 hover:bg-secondary/40 transition-colors text-left"
                >
                  <sug.icon className={cn("w-3 h-3 flex-shrink-0", sug.cor)} />
                  <span className="text-[11px] text-muted-foreground truncate">{sug.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="px-3 py-3 border-t border-border/50">
          <div className="flex gap-2">
            <input
              ref={chatInputRef}
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); sendChatMessage(); }}}
              placeholder="Pergunte sobre trading..."
              disabled={chatLoading}
              className="flex-1 bg-secondary/30 border border-border/50 rounded-xl px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:border-purple-500/50"
            />
            <Button
              onClick={() => sendChatMessage()}
              disabled={chatLoading || !chatInput.trim()}
              size="sm"
              className="bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-400 hover:to-pink-500 rounded-xl"
            >
              <Send className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}