"use client"

import { useState, useEffect, useRef } from "react"
import { 
  Play, Square, RefreshCw, Zap, 
  TrendingUp, TrendingDown, Activity, 
  BarChart3, X, Trash2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TradingChart } from "@/components/apps/TradingChart"

// ============================================
// INTERFACES
// ============================================

interface RawCrypto {
  id: string
  energia?: number
  symbol?: string
  price?: number
  delta?: number
  tipo?: string
  candles?: any[]
  previsao?: number
  previsao_5s?: number
  previsao_15s?: number
  previsao_30s?: number
  previsao_60s?: number
}

interface Crypto {
  id: string
  symbol: string
  price: number
  energy: number
  delta: number
  candles: any[]
  previsao: number
  previsao_5s?: number
  previsao_15s?: number
  previsao_30s?: number
  previsao_60s?: number
}

interface CryptoAppProps {
  cryptos: RawCrypto[]
  executeCommand: (command: string) => Promise<string>
  onRefresh?: () => Promise<void>
  pausePolling?: () => void
  resumePolling?: () => void
  clearUnits?: () => void
  onCoinsRemoved?: (symbols: string[]) => void
}

interface ReportCoin {
  symbol: string
  acertos: number
  erros: number
  total: number
  acuracia: number
  confianca: number
  categoria: "recommended" | "learning" | "bad"
  id: number
}

interface DashboardStats {
  acuracia: number
  total_previsoes: number
  acertos: number
  melhores_horarios: Array<{ hora: string; total: number; acuracia: number }>
  performance_moedas: Array<{ symbol: string; total: number; acuracia: number }>
  tendencia: {
    ultima_hora: number
    direcao: "up" | "down" | "stable"
    variacao: number
  }
}

// ============================================
// HELPERS
// ============================================

const STORAGE_KEY = "trader_loaded_coins"

const availableCoins = [
  "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
  "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"
]

function getSignalAction(previsao: number) {
  const previsaoPercentual = Math.abs(previsao) * 1000
  const sinal = previsao > 0 ? previsaoPercentual : -previsaoPercentual

  if (sinal > 20)  return { text: "COMPRAR", color: "green", level: "strong" }
  if (sinal > 5)   return { text: "COMPRAR", color: "green", level: "moderate" }
  if (sinal < -20) return { text: "VENDER",  color: "red",   level: "strong" }
  if (sinal < -5)  return { text: "VENDER",  color: "red",   level: "moderate" }
  return { text: "AGUARDAR", color: "gray", level: "neutral" }
}

function parseValidCryptos(rawList: RawCrypto[]): Crypto[] {
  return (rawList ?? [])
    .filter(c => c.symbol && c.price !== undefined)
    .reduce((acc, c) => {
      const existingIndex = acc.findIndex(a => a.symbol === c.symbol)
      const previsao     = (c as any).previsao    ?? 0
      const previsao_5s  = (c as any).previsao_5s  ?? previsao
      const previsao_15s = (c as any).previsao_15s ?? previsao
      const previsao_30s = (c as any).previsao_30s ?? previsao
      const previsao_60s = (c as any).previsao_60s ?? previsao

      const mapped: Crypto = {
        id:          c.id,
        symbol:      c.symbol!,
        price:       c.price!,
        energy:      c.energia   ?? 0,
        delta:       c.delta     ?? 0,
        candles:     (c as any).candles ?? [],
        previsao,
        previsao_5s,
        previsao_15s,
        previsao_30s,
        previsao_60s,
      }

      if (existingIndex === -1) {
        acc.push(mapped)
      } else if (parseInt(c.id) > parseInt(acc[existingIndex].id)) {
        acc[existingIndex] = mapped
      }

      return acc
    }, [] as Crypto[])
}

// ============================================
// COMPONENT
// ============================================

export function CryptoApp({ 
  cryptos, 
  executeCommand, 
  onRefresh, 
  pausePolling, 
  resumePolling, 
  clearUnits,
  onCoinsRemoved,
}: CryptoAppProps) {

  // ── UI state ──────────────────────────────
  const [timeframe,           setTimeframe]           = useState(5)
  const [loading,             setLoading]             = useState<string | null>(null)
  const [isRunning,           setIsRunning]           = useState(false)
  const [chartType,           setChartType]           = useState<"candlestick" | "line" | "area">("candlestick")
  const [showIndicators,      setShowIndicators]      = useState(true)
  const [selectedCoinForChart,setSelectedCoinForChart]= useState<string>("BTCUSDT")
  const [selectedCoins,       setSelectedCoins]       = useState<string[]>(["BTCUSDT", "ETHUSDT"])
  const [showCoinSelector,    setShowCoinSelector]    = useState(false)
  const [chartKey,            setChartKey]            = useState(0)
  const [notification,        setNotification]        = useState<{ message: string; type: "success" | "error" | "info" } | null>(null)

  // ── Report modal ──────────────────────────
  const [showReportModal,       setShowReportModal]       = useState(false)
  const [reportData,            setReportData]            = useState<ReportCoin[]>([])
  const [selectedCoinsToRemove, setSelectedCoinsToRemove] = useState<string[]>([])
  const [isLoadingReport,       setIsLoadingReport]       = useState(false)

  // ── Clear coins modal ─────────────────────
  const [showClearCoinsModal, setShowClearCoinsModal] = useState(false)
  const [coinsToClear,        setCoinsToClear]        = useState<string[]>([])

  // ── Accuracy cache ────────────────────────
  const [accuracyCache, setAccuracyCache] = useState<Record<string, { acuracia: number; acertos: number; total: number }>>({})

  // ── Dashboard stats ───────────────────────
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
    acuracia: 0,
    total_previsoes: 0,
    acertos: 0,
    melhores_horarios: [],
    performance_moedas: [],
    tendencia: { ultima_hora: 0, direcao: "stable", variacao: 0 },
  })

  // ============================================
  // DERIVED DATA
  // ── A prop `cryptos` já chega filtrada pelo pai (page.tsx).
  // ── Não há blacklist local. Apenas processar e exibir.
  // ============================================

  const validCryptos = parseValidCryptos(cryptos)

  const selected      = validCryptos.find(c => c.symbol === selectedCoinForChart) ?? validCryptos[0] ?? null
  const total         = validCryptos.length
  const strongest     = [...validCryptos].sort((a, b) => b.energy - a.energy)[0] ?? null
  const positiveCount = validCryptos.filter(c => c.delta > 0).length
  const negativeCount = validCryptos.filter(c => c.delta < 0).length
  const bestSignal    = validCryptos[0] ?? null

  // ============================================
  // EFFECTS
  // ============================================

  // Persiste moedas selecionadas no localStorage
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const coins = JSON.parse(saved)
        if (Array.isArray(coins) && coins.length > 0) setSelectedCoins(coins)
      } catch {}
    }
  }, [])

  useEffect(() => {
    if (selectedCoins.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedCoins))
    }
  }, [selectedCoins])

  // Se a moeda selecionada no gráfico desapareceu (foi removida), troca para a primeira disponível
  useEffect(() => {
    if (total > 0 && !validCryptos.find(c => c.symbol === selectedCoinForChart)) {
      setSelectedCoinForChart(validCryptos[0].symbol)
    }
  }, [validCryptos, selectedCoinForChart, total])

  // Polling de acurácias a cada 5 s
  useEffect(() => {
    fetchAllAccuracies()
    const interval = setInterval(fetchAllAccuracies, 5000)
    return () => clearInterval(interval)
  }, [])

  // Atualiza acurácias quando o número de moedas muda
  useEffect(() => {
    if (total > 0) fetchAllAccuracies()
  }, [total])

  // Aviso de saída quando IA está rodando
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isRunning) return
      e.preventDefault()
      e.returnValue = "A IA ainda está rodando. Tem certeza?"
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isRunning])

  useEffect(() => {
  if (selected) {
    console.log("📊 PREVISÕES PARA O GRÁFICO:", {
      symbol: selected.symbol,
      prediction5s: selected.previsao_5s,
      prediction15s: selected.previsao_15s,
      prediction30s: selected.previsao_30s,
      prediction60s: selected.previsao_60s,
    })
    console.log("🔍 DADOS RECEBIDOS DO BACKEND:", {
      symbol: selected.symbol,
      previsao_5s: (selected as any).previsao_5s,
      previsao_15s: (selected as any).previsao_15s,
      previsao_30s: (selected as any).previsao_30s,
      previsao_60s: (selected as any).previsao_60s,
    })
  }
}, [selected])

  // ============================================
  // HELPERS
  // ============================================

  function showNotification(message: string, type: "success" | "error" | "info") {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  async function fetchAllAccuracies() {
    try {
      const result = await executeCommand("crypto report")
      const clean  = typeof result === "string" ? result.replace(/^rse>\s*/, "") : result
      const parsed = JSON.parse(clean)
      if (!Array.isArray(parsed)) return

      const cache: typeof accuracyCache = {}
      parsed.forEach((coin: ReportCoin) => {
        cache[coin.symbol] = { acuracia: coin.acuracia, acertos: coin.acertos, total: coin.total }
      })
      setAccuracyCache(cache)
    } catch {}
  }

  async function fetchPerformanceReport() {
    setIsLoadingReport(true)
    try {
      const result = await executeCommand("crypto report")
      const clean  = typeof result === "string" ? result.replace(/^rse>\s*/, "") : result
      const parsed = JSON.parse(clean)
      setReportData(Array.isArray(parsed) ? parsed : [])
      setSelectedCoinsToRemove([])
      setShowReportModal(true)
    } catch {
      showNotification("Erro ao gerar relatório de desempenho", "error")
    } finally {
      setIsLoadingReport(false)
    }
  }

  // ============================================
  // REMOVE HELPERS
  // ── Toda remoção segue o mesmo padrão:
  //   1. Chama o backend
  //   2. Avisa o pai via onCoinsRemoved (ele atualiza a blacklist)
  //   3. Atualiza selectedCoins / localStorage
  //   4. Força re-render do gráfico
  // ============================================

  async function doRemove(symbolsToRemove: string[]) {
    await executeCommand(`crypto remove ${symbolsToRemove.join(" ")}`)

    // Avisa o pai — ele vai filtrar `units` e a prop `cryptos` chegará limpa
    if (onCoinsRemoved) onCoinsRemoved(symbolsToRemove)

    const remaining = selectedCoins.filter(c => !symbolsToRemove.includes(c))
    setSelectedCoins(remaining)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(remaining))

    setChartKey(prev => prev + 1)
  }

  async function removeSelectedCoins() {
    if (selectedCoinsToRemove.length === 0) {
      showNotification("Nenhuma moeda selecionada para remover", "info")
      return
    }
    setLoading("remove")
    try {
      await doRemove(selectedCoinsToRemove)
      showNotification(`${selectedCoinsToRemove.length} moeda(s) removidas`, "success")
      setShowReportModal(false)
    } catch {
      showNotification("Erro ao remover moedas", "error")
    } finally {
      setLoading(null)
    }
  }

  async function keepOnlySelectedCoins() {
    const toRemove = reportData.map(c => c.symbol).filter(c => !selectedCoinsToRemove.includes(c))
    if (toRemove.length === 0) {
      showNotification("Nenhuma moeda para remover", "info")
      return
    }
    setLoading("keep")
    try {
      await doRemove(toRemove)
      showNotification(
        `Mantidas ${selectedCoinsToRemove.length} moedas. Removidas: ${toRemove.join(", ")}`,
        "success"
      )
      setShowReportModal(false)
    } catch {
      showNotification("Erro ao remover moedas", "error")
    } finally {
      setLoading(null)
    }
  }

  async function clearSelectedCoins() {
    if (coinsToClear.length === 0) {
      showNotification("Nenhuma moeda selecionada para remover", "info")
      return
    }
    setLoading("clear")
    try {
      await doRemove(coinsToClear)
      showNotification(`${coinsToClear.length} moeda(s) removidas`, "success")
      setShowClearCoinsModal(false)
      setCoinsToClear([])
    } catch {
      showNotification("Erro ao remover moedas", "error")
    } finally {
      setLoading(null)
    }
  }

  // ============================================
  // COMMANDS
  // ============================================

  async function handleCommand(command: string, buttonId: string) {
    setLoading(buttonId)

    // START
    if (command.includes("start")) {
      if (total === 0) {
        showNotification("Carregue moedas antes de iniciar a IA", "error")
        setLoading(null)
        return
      }
      setIsRunning(true)
      if (resumePolling) resumePolling()
      try {
        await executeCommand(command)
        showNotification("IA iniciada. Monitorando mercado em tempo real.", "success")
      } catch {
        showNotification("Erro ao iniciar IA", "error")
      }
      setLoading(null)
      return
    }

    // STOP
    if (command.includes("stop")) {
      setIsRunning(false)
      try {
        await executeCommand(command)
        await fetchPerformanceReport()
        showNotification("IA parada. Relatório de desempenho gerado.", "info")
      } catch {
        showNotification("Erro ao parar IA", "error")
      }
      setLoading(null)
      return
    }

    // outros
    try {
      await executeCommand(command)

      if (command.includes("spawn")) {
        showNotification(`${selectedCoins.length} moeda(s) carregadas.`, "success")
        if (resumePolling) resumePolling()
        localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedCoins))
        if (onRefresh) await onRefresh()
        setChartKey(prev => prev + 1)
        setLoading(null)
        return
      }

      if (command.includes("signal")) {
        if (bestSignal) {
          const signal = getSignalAction(bestSignal.previsao)
          showNotification(
            `SINAL: ${signal.text} ${bestSignal.symbol.replace("USDT", "")} - Confiança: ${Math.abs(bestSignal.previsao).toFixed(0)}%`,
            "info"
          )
        } else {
          showNotification("Carregue moedas primeiro para obter sinais", "info")
        }
      }
    } catch {
      showNotification("Erro ao executar comando", "error")
    } finally {
      setLoading(null)
    }
  }

  // ============================================
  // RENDER
  // ============================================

  return (
    <div className="space-y-6">

      {/* Toast */}
      {notification && (
        <div className={cn(
          "fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg animate-in slide-in-from-right text-sm",
          notification.type === "success" && "bg-green-500/20 border border-green-500/30 text-green-400",
          notification.type === "error"   && "bg-red-500/20   border border-red-500/30   text-red-400",
          notification.type === "info"    && "bg-blue-500/20  border border-blue-500/30  text-blue-400"
        )}>
          {notification.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 flex items-center justify-center">
            <span className="text-white text-sm font-bold">AI</span>
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">TRADER AI</h2>
            <p className="text-xs text-muted-foreground">Inteligência Adaptativa para Mercados</p>
          </div>
        </div>
        {isRunning && (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30 animate-pulse">
            <Activity className="h-3 w-3" />
            MONITORANDO
          </span>
        )}
      </div>

      {/* Main Signal Card */}
      {total > 0 && selected && (() => {
        const signal     = getSignalAction(selected.previsao)
        const color      = signal.color === "green" ? "#00e676" : signal.color === "red" ? "#ff3d57" : "#f59e0b"
        const conf       = Math.min(99, Math.abs(selected.previsao) * 1000)
        const coinAcc    = accuracyCache[selected.symbol]

        return (
          <div className="rounded-lg overflow-hidden border-2 transition-all relative"
            style={{ background: "linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 100%)", borderColor: color }}>
            <div className="absolute inset-0 opacity-30"
              style={{ background: `radial-gradient(circle at 30% 50%, ${color}20 0%, transparent 70%)` }} />

            <div className="relative p-5">
              {/* Header row */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full flex items-center justify-center"
                    style={{ background: `${color}20`, border: `1px solid ${color}` }}>
                    <span className="text-lg">
                      {signal.color === "green" ? "📈" : signal.color === "red" ? "📉" : "⏸"}
                    </span>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">RECOMENDAÇÃO IA</div>
                    <div className="text-xl font-bold" style={{ color }}>{signal.text}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">Acurácia ({selected.symbol.replace("USDT", "")})</div>
                  <div className="text-2xl font-bold tabular-nums"
                    style={{ color: (coinAcc?.acuracia ?? 0) >= 55 ? "#00e676" : (coinAcc?.acuracia ?? 0) >= 45 ? "#f59e0b" : "#ff3d57" }}>
                    {coinAcc?.acuracia ?? 0}%
                  </div>
                  <div className="text-xs text-muted-foreground">{coinAcc?.acertos ?? 0}/{coinAcc?.total ?? 0} acertos</div>
                </div>
              </div>

              {/* Moeda e confiança */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-2xl font-bold text-white">{selected.symbol.replace("USDT", "")}</div>
                  <div className="text-sm text-muted-foreground">${selected.price.toLocaleString()}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">Confiança IA</div>
                  <div className="text-3xl font-bold tabular-nums"
                    style={{ color: conf >= 60 ? "#00e676" : conf >= 30 ? "#f59e0b" : "#ff3d57" }}>
                    {conf.toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Barra de confiança */}
              <div className="h-1.5 rounded-full overflow-hidden bg-gray-800 mb-4">
                <div className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${conf}%`,
                    background: `linear-gradient(90deg, ${color} 0%, ${color}80 100%)`
                  }} />
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Tendência IA:</span>
                  <span style={{
                    color: dashboardStats.tendencia.direcao === "up" ? "#00e676"
                         : dashboardStats.tendencia.direcao === "down" ? "#ff3d57" : "#f59e0b"
                  }}>
                    {dashboardStats.tendencia.direcao === "up" ? "Melhorando"
                   : dashboardStats.tendencia.direcao === "down" ? "Piorando" : "Estável"}
                    {dashboardStats.tendencia.variacao > 0 && ` +${dashboardStats.tendencia.variacao}%`}
                  </span>
                </div>
                <div className="text-muted-foreground">Baseado em {coinAcc?.total ?? 0} análises</div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* PREVISÕES MULTI-HORIZONTE - Visual Premium */}
      {selected && (
        <div className="rounded-xl bg-gradient-to-r from-secondary/50 to-secondary/30 border border-border/50 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">PREVISÕES POR HORIZONTE</span>
            </div>
            <div className="text-[10px] text-muted-foreground">
              Baseado em {accuracyCache[selected.symbol]?.total || 0} análises
            </div>
          </div>
          
          {/* Barras de previsão - Versão com PREÇO + % */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { time: "5s", value: (selected as any).previsao_5s ?? selected.previsao, label: "previsao_5s" },
              { time: "15s", value: (selected as any).previsao_15s ?? selected.previsao, label: "previsao_15s" },
              { time: "30s", value: (selected as any).previsao_30s ?? selected.previsao, label: "previsao_30s" },
              { time: "60s", value: (selected as any).previsao_60s ?? selected.previsao, label: "previsao_60s" },
            ].map((pred, i) => {
              const value = pred.value ?? 0
              const isPositive = value >= 0
              const intensidade = Math.min(1, Math.abs(value) / 2)
              const precoAlvo = selected.price * (1 + value / 100)
              
              return (
                <div 
                  key={i}
                  className="rounded-xl p-3 transition-all hover:scale-105 cursor-help"
                  style={{
                    background: isPositive 
                      ? `linear-gradient(135deg, rgba(0, 230, 118, ${0.15 + intensidade * 0.3}) 0%, rgba(0, 230, 118, ${0.05}) 100%)`
                      : `linear-gradient(135deg, rgba(255, 61, 87, ${0.15 + intensidade * 0.3}) 0%, rgba(255, 61, 87, 0.05) 100%)`,
                    border: `1px solid ${isPositive ? '#00e676' : '#ff3d57'}`
                  }}
                >
                  <div className="text-center">
                    <div className="text-[10px] text-muted-foreground mb-1">{pred.time}</div>
                    {/* ⭐ Mostra o PERCENTUAL */}
                    <div className={`text-lg font-bold font-mono ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                      {value > 0 ? "+" : ""}{value.toFixed(2)}%
                    </div>
                    {/* ⭐ Mostra o PREÇO ALVO */}
                    <div className="text-[10px] text-muted-foreground mt-1">
                      ≈ ${precoAlvo.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                    <div className="h-1 w-full bg-gray-800 rounded-full mt-2 overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${isPositive ? 'bg-green-400' : 'bg-red-400'}`}
                        style={{ width: `${Math.min(100, Math.abs(value) * 50)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          
          {/* Footer com direção dominante */}
          <div className="flex items-center justify-between pt-3 mt-2 border-t border-border/30">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                (() => {
                  const values = [
                    (selected as any).previsao_5s,
                    (selected as any).previsao_15s,
                    (selected as any).previsao_30s,
                    (selected as any).previsao_60s
                  ].filter(v => v !== undefined)
                  const positives = values.filter(v => v > 0).length
                  const negatives = values.filter(v => v < 0).length
                  return positives > negatives ? 'bg-green-400' : negatives > positives ? 'bg-red-400' : 'bg-gray-400'
                })()
              }`} />
              <span className="text-[10px] text-muted-foreground">
                Tendência: {
                  (() => {
                    const values = [
                      (selected as any).previsao_5s,
                      (selected as any).previsao_15s,
                      (selected as any).previsao_30s,
                      (selected as any).previsao_60s
                    ].filter(v => v !== undefined)
                    const positives = values.filter(v => v > 0).length
                    const negatives = values.filter(v => v < 0).length
                    return positives > negatives ? "ALTA" : negatives > positives ? "BAIXA" : "LATERAL"
                  })()
                }
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-green-400" />
                <span className="text-[9px] text-muted-foreground">
                  {(() => {
                    const values = [
                      (selected as any).previsao_5s,
                      (selected as any).previsao_15s,
                      (selected as any).previsao_30s,
                      (selected as any).previsao_60s
                    ].filter(v => v !== undefined)
                    return values.filter(v => v > 0).length
                  })()} compras
                </span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-red-400" />
                <span className="text-[9px] text-muted-foreground">
                  {(() => {
                    const values = [
                      (selected as any).previsao_5s,
                      (selected as any).previsao_15s,
                      (selected as any).previsao_30s,
                      (selected as any).previsao_60s
                    ].filter(v => v !== undefined)
                    return values.filter(v => v < 0).length
                  })()} vendas
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { icon: <BarChart3 className="h-4 w-4" />,                               label: "MOEDAS",     value: total,         color: "" },
          { icon: <Zap className="h-4 w-4 text-cyan-400" />,                        label: "MAIS FORTE", value: strongest?.symbol?.replace("USDT","") ?? "-", color: "text-cyan-400" },
          { icon: <TrendingUp className="h-4 w-4 text-green-400" />,                label: "EM ALTA",    value: positiveCount, color: "text-green-400" },
          { icon: <TrendingDown className="h-4 w-4 text-red-400" />,                label: "EM BAIXA",   value: negativeCount, color: "text-red-400" },
        ].map(card => (
          <div key={card.label} className="rounded-lg border border-border/50 bg-secondary/30 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              {card.icon}
              <span className="text-xs">{card.label}</span>
            </div>
            <p className={cn("text-2xl font-bold mt-1", card.color)}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Timeframes */}
      <div className="flex gap-1">
        {[5, 10, 30, 60].map(tf => (
          <button key={tf} onClick={() => setTimeframe(tf)}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all",
              timeframe === tf
                ? "bg-amber-500/30 text-amber-400 border border-amber-500/40"
                : "bg-secondary/50 text-muted-foreground hover:bg-secondary/80"
            )}>
            {tf}s
          </button>
        ))}
      </div>

      {/* Chart controls */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-2 rounded-lg bg-secondary/20 border border-border/50">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">TIPO DE GRÁFICO</span>
            <div className="flex gap-1">
              {(["candlestick","line","area"] as const).map(type => (
                <button key={type} onClick={() => setChartType(type)}
                  className={cn(
                    "px-3 py-1 rounded-md text-xs font-medium transition-all",
                    chartType === type
                      ? "bg-purple-500/30 text-purple-400 border border-purple-500/40"
                      : "text-muted-foreground hover:bg-secondary/80"
                  )}>
                  {{ candlestick: "VELAS", line: "LINHA", area: "ÁREA" }[type]}
                </button>
              ))}
            </div>
          </div>
          <button onClick={() => setShowIndicators(!showIndicators)}
            className={cn(
              "px-2 py-1 rounded-md text-xs transition-all",
              showIndicators
                ? "bg-cyan-500/30 text-cyan-400 border border-cyan-500/40"
                : "text-muted-foreground"
            )}>
            {showIndicators ? "INDICADORES ATIVOS" : "INDICADORES INATIVOS"}
          </button>
        </div>
      )}

      {/* Trading Chart */}
      {selected && total > 0 && (
        <div className="rounded-lg border border-border/50 bg-secondary/20 p-2">
          <TradingChart
            key={`${selected.symbol}-${timeframe}-${chartKey}`}
            candles={selected.candles}
            currentPrice={selected.price}
            prediction={selected.previsao}
            prediction5s={selected.previsao_5s}
            prediction15s={selected.previsao_15s}
            prediction30s={selected.previsao_30s}
            prediction60s={selected.previsao_60s}
            timeframe={timeframe}
            symbol={selected.symbol}
            isActive={isRunning}
            chartType={chartType}
            showIndicators={showIndicators}
          />
        </div>
      )}

      {/* Coin selector bar */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-2 rounded-lg bg-secondary/20 border border-border/50">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">MOEDA NO GRÁFICO</span>
            <div className="flex flex-wrap gap-1">
              {validCryptos.map(c => (
                <button key={c.symbol} onClick={() => setSelectedCoinForChart(c.symbol)}
                  className={cn(
                    "px-3 py-1 rounded-md text-sm font-mono transition-all",
                    selectedCoinForChart === c.symbol
                      ? "bg-amber-500/30 text-amber-400 border border-amber-500/40"
                      : "text-muted-foreground hover:bg-secondary/80"
                  )}>
                  {c.symbol.replace("USDT", "")}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span>{total} ativa(s)</span>
          </div>
        </div>
      )}


      {/* Market list */}
      {total > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">ANÁLISE POR MOEDA</span>
            <span className="text-xs text-muted-foreground">{total} moedas</span>
          </div>
          <div className="rounded-lg border border-border/50 bg-secondary/40 p-2 space-y-1 max-h-64 overflow-y-auto">
            <div className="grid grid-cols-5 gap-2 text-[10px] font-medium text-muted-foreground uppercase pb-2 border-b border-border/30 px-2">
              <span>MOEDA</span>
              <span className="text-right">PREÇO</span>
              <span className="text-right">VARIAÇÃO 24H</span>
              <span className="text-right">CONFIANÇA IA</span>
              <span className="text-right">SINAL</span>
            </div>
            {validCryptos.map(c => {
              const signal = getSignalAction(c.previsao)
              return (
                <div key={c.id} className="grid grid-cols-5 gap-2 text-sm py-2 hover:bg-secondary/30 rounded px-2">
                  <span className="font-medium text-foreground">{c.symbol.replace("USDT", "")}</span>
                  <span className="text-right font-mono">${c.price.toFixed(2)}</span>
                  <span className={cn("text-right font-mono",
                    c.delta > 0 ? "text-green-400" : c.delta < 0 ? "text-red-400" : "text-muted-foreground")}>
                    {c.delta > 0 ? "+" : ""}{c.delta.toFixed(2)}%
                  </span>
                  <span className="text-right text-cyan-400 font-mono">
                    {(Math.abs(c.previsao) * 1000).toFixed(0)}%
                  </span>
                  <span className={cn(
                    "text-right text-xs font-bold px-2 py-0.5 rounded w-16 ml-auto",
                    signal.color === "green" && "bg-green-500/20 text-green-400",
                    signal.color === "red"   && "bg-red-500/20   text-red-400",
                    signal.color === "gray"  && "bg-gray-500/20  text-gray-400"
                  )}>
                    {signal.text}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {total === 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-8 text-center">
          <p className="text-amber-400 font-medium">Nenhuma moeda carregada</p>
          <p className="text-xs text-muted-foreground mt-2">
            Clique em CARREGAR para selecionar as moedas que deseja analisar
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-5 gap-3">
        <Button onClick={() => handleCommand("crypto start", "start")}
          disabled={loading !== null || total === 0}
          className="bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30">
          <Play className="h-4 w-4 mr-2" /> INICIAR IA
        </Button>
        <Button onClick={() => setShowCoinSelector(true)}
          disabled={loading !== null}
          className="bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30">
          <RefreshCw className="h-4 w-4 mr-2" /> CARREGAR
        </Button>
        <Button onClick={() => handleCommand("crypto signal", "signal")}
          disabled={loading !== null || total === 0}
          className="bg-purple-500/20 border border-purple-500/30 text-purple-400 hover:bg-purple-500/30">
          <Zap className="h-4 w-4 mr-2" /> SINAL
        </Button>
        <Button onClick={() => handleCommand("crypto stop", "stop")}
          disabled={loading !== null}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30">
          <Square className="h-4 w-4 mr-2" /> PARAR IA
        </Button>
        <Button onClick={() => { if (total === 0) { showNotification("Nenhuma moeda para remover", "info"); return }; setCoinsToClear([]); setShowClearCoinsModal(true) }}
          disabled={loading !== null || total === 0}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30">
          <Trash2 className="h-4 w-4 mr-2" /> LIMPAR
        </Button>
      </div>

      {/* Coin buttons (duplicate selector) */}
      <div className="flex flex-wrap gap-1">
        {validCryptos.map(c => (
          <button key={`${c.symbol}-${c.id}`} onClick={() => setSelectedCoinForChart(c.symbol)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm font-mono transition-all",
              selectedCoinForChart === c.symbol
                ? "bg-amber-500/30 text-amber-400 border border-amber-500/40 shadow-lg"
                : "bg-secondary/50 text-muted-foreground hover:bg-secondary/80"
            )}>
            {c.symbol.replace("USDT", "")}
          </button>
        ))}
      </div>

      {/* ── MODALS ─────────────────────────────────── */}

      {/* Coin Selector Modal */}
      {showCoinSelector && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-secondary rounded-xl p-6 w-96 border border-border shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Selecionar Moedas</h3>
              <button onClick={() => setShowCoinSelector(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Selecione as moedas que a IA vai analisar</p>
            <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto mb-4">
              {availableCoins.map(coin => (
                <label key={coin} className="flex items-center gap-2 p-2 rounded hover:bg-secondary/50 cursor-pointer">
                  <input type="checkbox" checked={selectedCoins.includes(coin)}
                    onChange={e => setSelectedCoins(e.target.checked
                      ? [...selectedCoins, coin]
                      : selectedCoins.filter(c => c !== coin))}
                    className="rounded border-border" />
                  <span className="text-sm font-mono">{coin}</span>
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCoinSelector(false)}>Cancelar</Button>
              <Button onClick={async () => {
                setShowCoinSelector(false)
                setLoading("spawn")
                const command = `crypto spawn ${selectedCoins.join(" ")}`
                await executeCommand(command)
                if (onRefresh) await onRefresh()
                setLoading(null)
                showNotification(`${selectedCoins.length} moeda(s) carregadas`, "success")
              }} className="bg-amber-500/20 text-amber-400 hover:bg-amber-500/30">
                Carregar ({selectedCoins.length})
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Clear Coins Modal */}
      {showClearCoinsModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-secondary rounded-xl p-6 w-[500px] max-w-[90vw] max-h-[80vh] overflow-y-auto border border-border shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">REMOVER MOEDAS</h3>
              <button onClick={() => setShowClearCoinsModal(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Selecione as moedas que deseja remover da lista</p>
            <div className="space-y-2 max-h-64 overflow-y-auto mb-4">
              {validCryptos.map(coin => (
                <label key={coin.symbol} className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30 border border-border/50 cursor-pointer hover:bg-secondary/50">
                  <input type="checkbox" checked={coinsToClear.includes(coin.symbol)}
                    onChange={e => setCoinsToClear(e.target.checked
                      ? [...coinsToClear, coin.symbol]
                      : coinsToClear.filter(c => c !== coin.symbol))}
                    className="rounded border-border w-4 h-4" />
                  <div className="flex-1">
                    <div className="font-bold text-foreground">{coin.symbol.replace("USDT", "")}</div>
                    <div className="text-xs text-muted-foreground">
                      Preço: ${coin.price.toFixed(2)} | Variação: {coin.delta > 0 ? "+" : ""}{coin.delta.toFixed(2)}%
                    </div>
                  </div>
                  <div className={cn("text-xs font-bold px-2 py-1 rounded",
                    coin.delta > 0 ? "text-green-400 bg-green-500/20" : "text-red-400 bg-red-500/20")}>
                    {coin.delta > 0 ? "↑" : "↓"} {Math.abs(coin.delta).toFixed(2)}%
                  </div>
                </label>
              ))}
            </div>
            <div className="flex gap-3 mt-6 pt-4 border-t border-border">
              <Button onClick={() => setCoinsToClear(validCryptos.map(c => c.symbol))}
                className="flex-1 bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/30">
                SELECIONAR TODAS
              </Button>
              <Button onClick={() => setCoinsToClear([])}
                className="flex-1 bg-gray-500/20 text-gray-400 hover:bg-gray-500/30 border border-gray-500/30">
                DESMARCAR TUDO
              </Button>
            </div>
            <div className="flex gap-3 mt-3">
              <Button variant="outline" onClick={() => setShowClearCoinsModal(false)} className="flex-1">Cancelar</Button>
              <Button onClick={clearSelectedCoins} disabled={coinsToClear.length === 0}
                className="flex-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30">
                REMOVER ({coinsToClear.length})
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Performance Report Modal */}
      {showReportModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 overflow-auto">
          <div className="bg-secondary rounded-xl p-6 w-[600px] max-w-[90vw] max-h-[80vh] overflow-y-auto border border-border shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">RELATÓRIO DE DESEMPENHO</h3>
              <button onClick={() => setShowReportModal(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            {isLoadingReport ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mx-auto" />
                <p className="text-sm text-muted-foreground mt-2">Analisando desempenho...</p>
              </div>
            ) : reportData.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground">Nenhuma moeda com dados suficientes para análise</p>
              </div>
            ) : (
              <>
                {(["recommended","learning","bad"] as const).map(cat => {
                  const coins = reportData.filter(c => c.categoria === cat)
                  if (coins.length === 0) return null
                  const cfg = {
                    recommended: { label: "MOEDAS RECOMENDADAS (Acurácia ≥ 55%)",    color: "green",  cls: "text-green-400",  bg: "bg-green-500/10  border-green-500/30" },
                    learning:    { label: "MOEDAS EM APRENDIZADO (45-55%)",           color: "yellow", cls: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30" },
                    bad:         { label: "MOEDAS COM DESEMPENHO BAIXO (≤ 45%)",      color: "red",    cls: "text-red-400",    bg: "bg-red-500/10    border-red-500/30" },
                  }[cat]
                  return (
                    <div key={cat} className="mb-4">
                      <h4 className={cn("text-sm font-bold mb-2", cfg.cls)}>{cfg.label}</h4>
                      <div className="space-y-2">
                        {coins.map(coin => (
                          <div key={coin.symbol} className={cn("flex items-center justify-between p-3 rounded-lg border", cfg.bg)}>
                            <div>
                              <div className="font-bold text-foreground">{coin.symbol.replace("USDT", "")}</div>
                              <div className="text-xs text-muted-foreground">{coin.acertos} acertos / {coin.erros} erros</div>
                            </div>
                            <div className="text-right">
                              <div className={cn("font-bold", cfg.cls)}>{coin.acuracia}%</div>
                              <div className={cn("text-xs", cfg.cls)}>
                                {{ recommended: "Recomendada", learning: "Em aprendizado", bad: "Desempenho baixo" }[cat]}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}

                <div className="flex gap-3 mt-6 pt-4 border-t border-border">
                  <Button onClick={() => setShowReportModal(false)}
                    className="flex-1 bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30">
                    FECHAR RELATÓRIO
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground text-center mt-3">
                  Moedas com acurácia acima de 55% são recomendadas. Abaixo de 45% considere remover.
                </p>
              </>
            )}
          </div>
        </div>
      )}

    </div>
  )
}