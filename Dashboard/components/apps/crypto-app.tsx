"use client"

import { useState, useEffect } from "react"
import { 
  Play, Square, RefreshCw, Zap, 
  TrendingUp, TrendingDown, Activity, 
  BarChart3, X 
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TradingChart } from "@/components/apps/TradingChart"

interface RawCrypto {
  id: string
  energia?: number
  symbol?: string
  price?: number
  delta?: number
  tipo?: string
  candles?: any[]
  previsao?: number
}

interface Crypto {
  id: string
  symbol: string
  price: number
  energy: number
  delta: number
  candles: any[]
  previsao: number
}

interface CryptoAppProps {
  cryptos: RawCrypto[]
  executeCommand: (command: string) => Promise<string>
  onRefresh?: () => Promise<void>
  pausePolling?: () => void
  resumePolling?: () => void
  clearUnits?: () => void
}

export function CryptoApp({ 
  cryptos, 
  executeCommand, 
  onRefresh, 
  pausePolling, 
  resumePolling, 
  clearUnits 
}: CryptoAppProps) {

  // ============================================
  // STATES
  // ============================================
  const [timeframe, setTimeframe] = useState(5)
  const [loading, setLoading] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [chartType, setChartType] = useState<"candlestick" | "line" | "area">("candlestick")
  const [showIndicators, setShowIndicators] = useState(true)
  const [selectedCoinForChart, setSelectedCoinForChart] = useState<string>("BTCUSDT")
  const [selectedCoins, setSelectedCoins] = useState<string[]>(["BTCUSDT", "ETHUSDT"])
  const [showCoinSelector, setShowCoinSelector] = useState(false)
  
  const [localCryptos, setLocalCryptos] = useState<RawCrypto[]>(cryptos)
  const [blockAutoSync, setBlockAutoSync] = useState(false)
  const [chartKey, setChartKey] = useState(0)
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null)

  const availableCoins = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT"
  ]

  // ============================================
  // HELPERS
  // ============================================
  const showNotification = (message: string, type: "success" | "error" | "info") => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  const clearAllData = () => {
    setBlockAutoSync(true)
    setLocalCryptos([])
    setTimeout(() => setBlockAutoSync(false), 500)
  }

  // ============================================
  // PROCESSAMENTO DE DADOS
  // ============================================
  const validCryptos: Crypto[] = (localCryptos ?? [])
    .filter(c => c.symbol && c.price !== undefined)
    .map(c => ({
      id: c.id,
      symbol: c.symbol!,
      price: c.price!,
      energy: c.energia ?? 0,
      delta: c.delta ?? 0,
      candles: (c as any).candles ?? [],
      previsao: (c as any).previsao ?? 0,
    }))

  const selected = validCryptos.find(c => c.symbol === selectedCoinForChart) ?? validCryptos[0] ?? null
  const total = validCryptos.length
  const strongest = [...validCryptos].sort((a, b) => b.energy - a.energy)[0] ?? null
  const positiveCount = validCryptos.filter(c => c.delta > 0).length
  const negativeCount = validCryptos.filter(c => c.delta < 0).length

  // Sinal principal (melhor recomendação do momento)
  const bestSignal = validCryptos[0]
  const getSignalAction = (previsao: number) => {
    if (previsao > 0.5) return { text: "COMPRAR", color: "green", level: "strong" }
    if (previsao > 0.2) return { text: "COMPRAR", color: "green", level: "moderate" }
    if (previsao < -0.5) return { text: "VENDER", color: "red", level: "strong" }
    if (previsao < -0.2) return { text: "VENDER", color: "red", level: "moderate" }
    return { text: "AGUARDAR", color: "gray", level: "neutral" }
  }

  // ============================================
  // EFFECTS
  // ============================================
  useEffect(() => {
    if (!blockAutoSync) {
      setLocalCryptos(cryptos)
    }
  }, [cryptos, blockAutoSync])

  useEffect(() => {
    setChartKey(prev => prev + 1)
  }, [timeframe])

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isRunning) return
      e.preventDefault()
      e.returnValue = "A IA ainda está rodando. Tem certeza?"
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isRunning])

  // ============================================
  // COMMANDS
  // ============================================
  const handleCommand = async (command: string, buttonId: string) => {
    setLoading(buttonId)
    
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
      } catch (error) {
        showNotification("Erro ao iniciar IA", "error")
      }
      
      setLoading(null)
      return
    }
    
    if (command.includes("stop")) {
      setIsRunning(false)
      if (pausePolling) pausePolling()
      clearAllData()
      if (clearUnits) clearUnits()
      
      try {
        await executeCommand(command)
        showNotification("IA pausada. Todas as moedas foram removidas.", "info")
      } catch (error) {
        showNotification("Erro ao pausar IA", "error")
      }
      
      await new Promise(resolve => setTimeout(resolve, 3000))
      if (onRefresh) await onRefresh()
      if (resumePolling) resumePolling()
      
      setLoading(null)
      return
    }
    
    try {
      await executeCommand(command)
      
      if (command.includes("spawn")) {
        showNotification(`${selectedCoins.length} moeda(s) carregadas. Clique em INICIAR para começar.`, "success")
        if (resumePolling) resumePolling()
        if (onRefresh) await onRefresh()
      }
      
      if (command.includes("signal")) {
        if (bestSignal) {
          const signal = getSignalAction(bestSignal.previsao)
          showNotification(`SINAL: ${signal.text} ${bestSignal.symbol.replace("USDT", "")} - Confiança: ${Math.abs(bestSignal.previsao * 100).toFixed(0)}%`, "info")
        } else {
          showNotification("Carregue moedas primeiro para obter sinais", "info")
        }
      }
    } catch (error) {
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
      {/* Toast Notification */}
      {notification && (
        <div className={cn(
          "fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg animate-in slide-in-from-right text-sm",
          notification.type === "success" && "bg-green-500/20 border border-green-500/30 text-green-400",
          notification.type === "error" && "bg-red-500/20 border border-red-500/30 text-red-400",
          notification.type === "info" && "bg-blue-500/20 border border-blue-500/30 text-blue-400"
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
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30 animate-pulse">
              <Activity className="h-3 w-3" />
              MONITORANDO
            </span>
          )}
        </div>
      </div>

      {/* Main Signal Card - Destaque principal */}
      {total > 0 && bestSignal && (
        <div className={cn(
          "rounded-lg p-5 text-center border-2 transition-all",
          getSignalAction(bestSignal.previsao).color === "green" && "border-green-500/50 bg-green-500/10",
          getSignalAction(bestSignal.previsao).color === "red" && "border-red-500/50 bg-red-500/10",
          getSignalAction(bestSignal.previsao).color === "gray" && "border-gray-500/30 bg-gray-500/5"
        )}>
          <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider">RECOMENDAÇÃO DO MOMENTO</div>
          <div className={cn(
            "text-3xl font-bold mb-1",
            getSignalAction(bestSignal.previsao).color === "green" && "text-green-400",
            getSignalAction(bestSignal.previsao).color === "red" && "text-red-400",
            getSignalAction(bestSignal.previsao).color === "gray" && "text-gray-400"
          )}>
            {getSignalAction(bestSignal.previsao).text}
          </div>
          <div className="text-sm text-muted-foreground">
            {bestSignal.symbol.replace("USDT", "")} • Confiança: {Math.abs(bestSignal.previsao * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-muted-foreground mt-2">
            Baseado em análise da IA adaptativa
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <BarChart3 className="h-4 w-4" />
            <span className="text-xs">MOEDAS</span>
          </div>
          <p className="text-2xl font-bold mt-1">{total}</p>
        </div>
        
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Zap className="h-4 w-4 text-cyan-400" />
            <span className="text-xs">MAIS FORTE</span>
          </div>
          <p className="text-xl font-bold mt-1 text-cyan-400">{strongest?.symbol?.replace("USDT", "") ?? "-"}</p>
        </div>
        
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingUp className="h-4 w-4 text-green-400" />
            <span className="text-xs">EM ALTA</span>
          </div>
          <p className="text-2xl font-bold mt-1 text-green-400">{positiveCount}</p>
        </div>
        
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingDown className="h-4 w-4 text-red-400" />
            <span className="text-xs">EM BAIXA</span>
          </div>
          <p className="text-2xl font-bold mt-1 text-red-400">{negativeCount}</p>
        </div>
      </div>

      {/* Timeframes */}
      <div className="flex gap-1">
        {[5, 10, 30, 60].map(tf => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-all",
              timeframe === tf 
                ? "bg-amber-500/30 text-amber-400 border border-amber-500/40" 
                : "bg-secondary/50 text-muted-foreground hover:bg-secondary/80"
            )}
          >
            {tf}s
          </button>
        ))}
      </div>

      {/* Chart Type & Indicators */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-2 rounded-lg bg-secondary/20 border border-border/50">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">TIPO DE GRÁFICO</span>
            <div className="flex gap-1">
              {[
                { type: "candlestick", label: "VELAS" },
                { type: "line", label: "LINHA" },
                { type: "area", label: "ÁREA" }
              ].map(({ type, label }) => (
                <button
                  key={type}
                  onClick={() => setChartType(type as any)}
                  className={cn(
                    "px-3 py-1 rounded-md text-xs font-medium transition-all",
                    chartType === type 
                      ? "bg-purple-500/30 text-purple-400 border border-purple-500/40" 
                      : "text-muted-foreground hover:bg-secondary/80"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          
          <button
            onClick={() => setShowIndicators(!showIndicators)}
            className={cn(
              "px-2 py-1 rounded-md text-xs transition-all",
              showIndicators 
                ? "bg-cyan-500/30 text-cyan-400 border border-cyan-500/40" 
                : "text-muted-foreground"
            )}
          >
            {showIndicators ? "INDICADORES ATIVOS" : "INDICADORES INATIVOS"}
          </button>
        </div>
      )}

      {/* Trading Chart */}
      {selected && total > 0 && (
        <div className="rounded-lg border border-border/50 bg-secondary/20 p-2">
          <TradingChart
            key={chartKey}
            candles={selected.candles}
            currentPrice={selected.price}
            prediction={selected.previsao}
            timeframe={timeframe}
            symbol={selected.symbol}
            isActive={isRunning}
            chartType={chartType}
            showIndicators={showIndicators}
          />
        </div>
      )}

      {/* Moeda Selector */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 p-2 rounded-lg bg-secondary/20 border border-border/50">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">MOEDA NO GRÁFICO</span>
            <div className="flex flex-wrap gap-1">
              {validCryptos.map(c => (
                <button
                  key={c.symbol}
                  onClick={() => setSelectedCoinForChart(c.symbol)}
                  className={cn(
                    "px-3 py-1 rounded-md text-sm font-mono transition-all",
                    selectedCoinForChart === c.symbol 
                      ? "bg-amber-500/30 text-amber-400 border border-amber-500/40" 
                      : "text-muted-foreground hover:bg-secondary/80"
                  )}
                >
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

      {/* Market List */}
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
            {validCryptos.map((c) => {
              const signal = getSignalAction(c.previsao)
              return (
                <div key={c.id} className="grid grid-cols-5 gap-2 text-sm py-2 hover:bg-secondary/30 rounded px-2">
                  <span className="font-medium text-foreground">{c.symbol.replace("USDT", "")}</span>
                  <span className="text-right font-mono">${c.price.toFixed(2)}</span>
                  <span className={cn(
                    "text-right font-mono",
                    c.delta > 0 ? "text-green-400" : c.delta < 0 ? "text-red-400" : "text-muted-foreground"
                  )}>
                    {c.delta > 0 ? "+" : ""}{c.delta.toFixed(2)}%
                  </span>
                  <span className="text-right text-cyan-400 font-mono">{Math.abs(c.previsao * 100).toFixed(0)}%</span>
                  <span className={cn(
                    "text-right text-xs font-bold px-2 py-0.5 rounded w-16 ml-auto",
                    signal.color === "green" && "bg-green-500/20 text-green-400",
                    signal.color === "red" && "bg-red-500/20 text-red-400",
                    signal.color === "gray" && "bg-gray-500/20 text-gray-400"
                  )}>
                    {signal.text}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {total === 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-8 text-center">
          <p className="text-amber-400 font-medium">Nenhuma moeda carregada</p>
          <p className="text-xs text-muted-foreground mt-2">
            Clique em CARREGAR para selecionar as moedas que deseja analisar
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-4 gap-3">
        <Button 
          onClick={() => handleCommand("crypto start", "start")} 
          disabled={loading !== null || total === 0}
          className="bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30"
        >
          <Play className="h-4 w-4 mr-2" />
          INICIAR IA
        </Button>
        
        <Button 
          onClick={() => setShowCoinSelector(true)} 
          disabled={loading !== null}
          className="bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          CARREGAR MOEDAS
        </Button>
        
        <Button 
          onClick={() => handleCommand("crypto signal", "signal")} 
          disabled={loading !== null || total === 0}
          className="bg-purple-500/20 border border-purple-500/30 text-purple-400 hover:bg-purple-500/30"
        >
          <Zap className="h-4 w-4 mr-2" />
          OBTER SINAL
        </Button>
        
        <Button 
          onClick={() => handleCommand("crypto stop", "stop")} 
          disabled={loading !== null}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30"
        >
          <Square className="h-4 w-4 mr-2" />
          PARAR IA
        </Button>
      </div>

      {/* Coin Selector Modal */}
      {showCoinSelector && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-secondary rounded-xl p-6 w-96 border border-border shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Selecionar Moedas</h3>
              <button 
                onClick={() => setShowCoinSelector(false)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <p className="text-xs text-muted-foreground mb-3">
              Selecione as moedas que a IA vai analisar
            </p>
            
            <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto mb-4">
              {availableCoins.map(coin => (
                <label key={coin} className="flex items-center gap-2 p-2 rounded hover:bg-secondary/50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedCoins.includes(coin)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedCoins([...selectedCoins, coin])
                      } else {
                        setSelectedCoins(selectedCoins.filter(c => c !== coin))
                      }
                    }}
                    className="rounded border-border"
                  />
                  <span className="text-sm font-mono">{coin}</span>
                </label>
              ))}
            </div>
            
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCoinSelector(false)}>
                Cancelar
              </Button>
              <Button 
                onClick={async () => {
                  setShowCoinSelector(false)
                  setLoading("spawn")
                  
                  const command = `crypto spawn ${selectedCoins.join(" ")}`
                  await executeCommand(command)
                  
                  if (onRefresh) await onRefresh()
                  setLoading(null)
                  
                  showNotification(`${selectedCoins.length} moeda(s) carregadas`, "success")
                }}
                className="bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
              >
                Carregar ({selectedCoins.length})
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}