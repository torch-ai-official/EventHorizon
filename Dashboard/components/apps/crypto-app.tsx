"use client"

import { useState, useEffect, useRef } from "react"
import { Binary, Loader2, TrendingUp, TrendingDown, Activity, Zap, BarChart3, Play, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts"
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
}

export function CryptoApp({ cryptos, executeCommand }: CryptoAppProps) {

  console.log("units recebidos:", cryptos?.length, cryptos?.[0])

  const [timeframe, setTimeframe] = useState(5)
  const [loading, setLoading] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [priceHistory, setPriceHistory] = useState<{ time: string; avgDelta: number }[]>([])

  // ── Normaliza dados recebidos ──────────────────────────────────────────────
  const validCryptos: Crypto[] = (cryptos ?? [])
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

    

  // Moeda selecionada (primeira da lista)
  const selected = validCryptos[0] ?? null

  // ── Métricas globais ───────────────────────────────────────────────────────
  const total = validCryptos.length
  const strongest = [...validCryptos].sort((a, b) => b.energy - a.energy)[0] ?? null
  const avgDelta = total > 0
    ? validCryptos.reduce((acc, c) => acc + c.delta, 0) / total
    : 0
  const avgPrice = total > 0
    ? validCryptos.reduce((acc, c) => acc + c.price, 0) / total
    : 0
  const positiveCount = validCryptos.filter(c => c.delta > 0).length
  const negativeCount = validCryptos.filter(c => c.delta < 0).length

  // ── Histórico de delta para o gráfico de barras ────────────────────────────
  useEffect(() => {
    if (total === 0) return
    const interval = setInterval(() => {
      const now = new Date().toLocaleTimeString("pt-BR", {
        hour: "2-digit", minute: "2-digit", second: "2-digit"
      })
      setPriceHistory(prev => [...prev, { time: now, avgDelta }].slice(-20))
    }, 1000)
    return () => clearInterval(interval)
  }, [avgDelta, total])

  // ── Aviso ao sair com app rodando ──────────────────────────────────────────
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isRunning) return
      e.preventDefault()
      e.returnValue = "Crypto ainda está rodando. Sair?"
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isRunning])

  // ── Handler de comandos ────────────────────────────────────────────────────
  const handleCommand = async (command: string, buttonId: string) => {
    setLoading(buttonId)
    if (command.includes("start")) setIsRunning(true)
    if (command.includes("stop")) {
      setIsRunning(false)
      setPriceHistory([]) // limpa histórico ao parar
    }

    try {
      const result = await executeCommand(command)
      setLastResult(result)

      await executeCommand("refresh")
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-6">

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Binary className="h-5 w-5 text-amber-400" />
          <span className="text-sm font-medium text-foreground">Crypto Market</span>
        </div>
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse">
              <Activity className="h-3 w-3" />
              Running
            </span>
          )}
          <span className={cn(
            "px-3 py-1 rounded-full text-xs font-medium",
            avgDelta > 0 ? "bg-green-500/20 text-green-400 border border-green-500/30"
              : avgDelta < 0 ? "bg-red-500/20 text-red-400 border border-red-500/30"
              : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
          )}>
            {avgDelta > 0 ? "Alta" : avgDelta < 0 ? "Baixa" : "Neutro"}
          </span>
        </div>
      </div>

      {/* ── Métricas ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: <BarChart3 className="h-4 w-4 text-amber-400" />, label: "Moedas", value: total, color: "amber" },
          { icon: <Zap className="h-4 w-4 text-cyan-400" />, label: "Mais Forte", value: strongest?.symbol ?? "-", color: "cyan" },
          { icon: <TrendingUp className="h-4 w-4 text-green-400" />, label: "Em Alta", value: positiveCount, color: "green" },
          { icon: <TrendingDown className="h-4 w-4 text-red-400" />, label: "Em Baixa", value: negativeCount, color: "red" },
        ].map(({ icon, label, value, color }) => (
          <div key={label} className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {icon}
                <span className="text-xs font-medium text-muted-foreground">{label}</span>
              </div>
              <p className={`text-2xl font-bold text-${color}-400`}>{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Timeframe selector ────────────────────────────────────────────── */}
      <div className="flex gap-2">
        {[5, 10, 30, 60].map(tf => (
          <Button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className={cn(
              "text-xs px-3 py-1",
              timeframe === tf ? "bg-amber-500/30 text-amber-400 border border-amber-500/40" : "bg-secondary"
            )}
          >
            {tf}s
          </Button>
        ))}
      </div>

      {/* ── TradingChart ──────────────────────────────────────────────────── */}
      {selected && (
        <div className="rounded-lg border border-border/50 bg-secondary/20 p-3">
          <TradingChart
            candles={selected.candles}        // ✅ todos os candles sem filtro
            currentPrice={selected.price}     // ✅ preço em tempo real direto da Binance
            prediction={selected.previsao}
            timeframe={timeframe}
            symbol={selected.symbol}
          />
        </div>
      )}

      {/* ── Gráfico de delta ──────────────────────────────────────────────── */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Evolução do Mercado</span>
          <span className={cn("font-medium", avgDelta > 0 ? "text-green-400" : avgDelta < 0 ? "text-red-400" : "text-muted-foreground")}>
            {avgDelta > 0 ? "+" : ""}{avgDelta.toFixed(2)}%
          </span>
        </div>
        <div className="h-36 rounded-lg border border-border/50 bg-secondary/20 p-3">
          {priceHistory.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priceHistory}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#aaa" }} />
                <YAxis tick={{ fontSize: 10, fill: "#aaa" }} />
                <Tooltip />
                <Bar dataKey="avgDelta" radius={[4, 4, 0, 0]}>
                  {priceHistory.map((entry, i) => (
                    <Cell key={i} fill={entry.avgDelta >= 0 ? "#22c55e" : "#ef4444"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              Aguardando dados...
            </div>
          )}
        </div>
      </div>

      {/* ── Lista de moedas ───────────────────────────────────────────────── */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Mercado</span>
          <span className="text-muted-foreground">{total} moedas</span>
        </div>
        <div className="rounded-lg border border-border/50 bg-secondary/40 p-3 space-y-2 max-h-48 overflow-y-auto">
          {validCryptos.length > 0 && (
            <div className="flex justify-between text-[10px] font-medium text-muted-foreground uppercase tracking-wider pb-2 border-b border-border/30">
              <span className="w-16">Symbol</span>
              <span className="w-20 text-right">Preço</span>
              <span className="w-16 text-right">Delta</span>
              <span className="w-14 text-right">Energia</span>
              <span className="w-12 text-right">Sinal</span>
            </div>
          )}
          {validCryptos.map((c) => {
            const trendScore = c.energy * Math.sign(c.delta)
            return (
              <div key={c.id} className="flex justify-between text-sm font-mono items-center py-1 hover:bg-secondary/40 rounded px-1">
                <span className="w-16 font-medium text-foreground">{c.symbol}</span>
                <span className="w-20 text-right text-white">${c.price.toFixed(2)}</span>
                <span className={cn("w-16 text-right font-medium flex items-center justify-end gap-1",
                  c.delta > 0 ? "text-green-400" : c.delta < 0 ? "text-red-400" : "text-muted-foreground"
                )}>
                  {c.delta > 0 ? <TrendingUp className="h-3 w-3" /> : c.delta < 0 ? <TrendingDown className="h-3 w-3" /> : null}
                  {c.delta.toFixed(2)}%
                </span>
                <span className="w-14 text-right text-cyan-400">{c.energy.toFixed(1)}</span>
                <span className={cn("w-12 text-right text-xs font-bold px-2 py-0.5 rounded",
                  trendScore > 0 ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                )}>
                  {trendScore > 0 ? "BUY" : "SELL"}
                </span>
              </div>
            )
          })}
          {total === 0 && (
            <p className="text-xs text-center text-muted-foreground py-4">Nenhuma moeda carregada</p>
          )}
        </div>
      </div>

      {/* ── Botões ────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-3">
        <Button onClick={() => handleCommand("crypto start", "start")} disabled={loading !== null}
          className="bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30">
          {loading === "start" ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
          Start
        </Button>
        <Button onClick={() => handleCommand("crypto spawn all", "spawn")} disabled={loading !== null}
          className="bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30">
          {loading === "spawn" ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          Load Coins
        </Button>
        <Button onClick={() => handleCommand("crypto signal", "signal")} disabled={loading !== null}
          className="bg-purple-500/20 border border-purple-500/30 text-purple-400 hover:bg-purple-500/30">
          {loading === "signal" ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
          Signal
        </Button>
        <Button onClick={() => handleCommand("crypto stop", "stop")} disabled={loading !== null}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30">
          {loading === "stop" ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Activity className="h-4 w-4 mr-2" />}
          Stop
        </Button>
      </div>

      {/* ── Último resultado ──────────────────────────────────────────────── */}
      {lastResult && (
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-4">
          <p className="text-xs text-muted-foreground mb-2">Último Resultado:</p>
          <p className="text-sm font-mono whitespace-pre-line text-foreground">{lastResult}</p>
        </div>
      )}

    </div>
  )
}