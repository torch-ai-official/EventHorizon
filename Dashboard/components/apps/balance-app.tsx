"use client"

import { useState, useEffect, useRef } from "react"
import { Scale, Zap, TrendingUp, TrendingDown, Play, Square, RefreshCw, FileText, Loader2, Activity } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"

interface Unit {
  id: string
  energy: number
  state?: string
}

interface BalanceAppProps {
  units: Unit[]
  totalEnergy: number
  executeCommand: (command: string) => Promise<string>
}

export function BalanceApp({
  units,
  totalEnergy,
  executeCommand
}: BalanceAppProps) {
  const [unitsConfig, setUnitsConfig] = useState("")
  const [resourceConfig, setResourceConfig] = useState("")
  const [goalConfig, setGoalConfig] = useState("")
  const [loading, setLoading] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const isConfigured =
    unitsConfig.trim() !== "" && resourceConfig.trim() !== "" && goalConfig.trim() !== ""
  const [configApplied, setConfigApplied] = useState(false)
  
  // State for running indicator
  const [isRunning, setIsRunning] = useState(false)
  
  // History for chart
  const [history, setHistory] = useState<{ time: string; avg: number; spread: number }[]>([])
  const historyRef = useRef(history)
  historyRef.current = history

  const averageEnergy = units.length > 0 
    ? Math.round(totalEnergy / units.length) 
    : 0
  
  const maxEnergy = units.length > 0 
    ? Math.max(...units.map(u => u.energy)) 
    : 0
  
  const minEnergy = units.length > 0 
    ? Math.min(...units.map(u => u.energy)) 
    : 0

  const energySpread = maxEnergy - minEnergy
  const isBalanced = energySpread <= 10

  // Update history when data changes
  useEffect(() => {
    if (units.length === 0) return
    
    const now = new Date().toLocaleTimeString("pt-BR", { 
      hour: "2-digit", 
      minute: "2-digit",
      second: "2-digit"
    })
    
    setHistory(prev => {
      const newHistory = [...prev, { time: now, avg: averageEnergy, spread: energySpread }]
      return newHistory.slice(-20) // Keep last 20 points
    })
  }, [units, averageEnergy, energySpread])

  // Alert on page leave if running
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isRunning) {
        e.preventDefault()
        e.returnValue = "O Balance ainda está em execução. Tem certeza que deseja sair?"
        return e.returnValue
      }
    }
    
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [isRunning])

  const handleCommand = async (command: string, buttonId: string) => {
    setLoading(buttonId)
    
    // Track running state
    if (command.includes("start") || command.includes("run")) {
      setIsRunning(true)
    } else if (command.includes("stop")) {
      setIsRunning(false)
    }
    
    try {
      const result = await executeCommand(command)
      setLastResult(result)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Status Badge with Running Indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Scale className="h-5 w-5 text-neon-blue" />
          <span className="text-sm font-medium text-foreground">Status do Balanceamento</span>
        </div>
        <div className="flex items-center gap-2">
          {/* Running Indicator */}
          {isRunning && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-neon-blue/20 text-neon-blue border border-neon-blue/30 animate-pulse">
              <Activity className="h-3 w-3 animate-pulse" />
              Running
            </span>
          )}
          <span className={cn(
            "px-3 py-1 rounded-full text-xs font-medium transition-all duration-300",
            isBalanced 
              ? "bg-green-500/20 text-green-400 border border-green-500/30" 
              : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
          )}>
            {isBalanced ? "Balanceado" : "Desbalanceado"}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Average Energy */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-neon-blue/50 hover:shadow-[0_0_15px_rgba(0,180,255,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-neon-blue/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-neon-blue" />
              <span className="text-xs font-medium text-muted-foreground">Energia Média</span>
            </div>
            <p className="text-2xl font-bold tracking-tight text-foreground">
              {averageEnergy}
            </p>
          </div>
        </div>

        {/* Max Energy */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-green-500/50 hover:shadow-[0_0_15px_rgba(34,197,94,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-400" />
              <span className="text-xs font-medium text-muted-foreground">Máxima</span>
            </div>
            <p className="text-2xl font-bold tracking-tight text-green-400">
              {maxEnergy}
            </p>
          </div>
        </div>

        {/* Min Energy */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-red-500/50 hover:shadow-[0_0_15px_rgba(239,68,68,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-400" />
              <span className="text-xs font-medium text-muted-foreground">Mínima</span>
            </div>
            <p className="text-2xl font-bold tracking-tight text-red-400">
              {minEnergy}
            </p>
          </div>
        </div>

        {/* Spread */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-neon-purple/50 hover:shadow-[0_0_15px_rgba(168,85,247,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-neon-purple/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-neon-purple" />
              <span className="text-xs font-medium text-muted-foreground">Spread</span>
            </div>
            <p className={cn(
              "text-2xl font-bold tracking-tight transition-colors duration-300",
              energySpread <= 10 ? "text-green-400" : energySpread <= 30 ? "text-amber-400" : "text-red-400"
            )}>
              {energySpread}
            </p>
          </div>
        </div>
      </div>

      {/* Energy Evolution Chart */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Evolução do Balanceamento</span>
          <span className="text-muted-foreground">{history.length} pontos</span>
        </div>
        <div className="h-40 rounded-lg border border-border/50 bg-secondary/20 p-3">
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="avgGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--neon-blue))" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="hsl(var(--neon-blue))" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="spreadGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--neon-purple))" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="hsl(var(--neon-purple))" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis 
                  dataKey="time" 
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis 
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: "hsl(var(--card))", 
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px"
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="avg" 
                  stroke="hsl(var(--neon-blue))" 
                  fill="url(#avgGradient)"
                  strokeWidth={2}
                  name="Média"
                />
                <Area 
                  type="monotone" 
                  dataKey="spread" 
                  stroke="hsl(var(--neon-purple))" 
                  fill="url(#spreadGradient)"
                  strokeWidth={2}
                  name="Spread"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              Aguardando dados para o gráfico...
            </div>
          )}
        </div>
      </div>

      {/* Energy Distribution Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Distribuição de Energia</span>
          <span className="text-muted-foreground">{units.length} unidades</span>
        </div>
        <div className="h-3 rounded-full bg-secondary overflow-hidden">
          <div 
            className="h-full rounded-full bg-gradient-to-r from-red-500 via-amber-500 to-green-500 transition-all duration-500"
            style={{ width: `${Math.min(100, 100 - energySpread)}%` }}
          />
        </div>
      </div>

      {/* Configuration */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-muted-foreground">Configuração</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={unitsConfig}
            onChange={(e) => setUnitsConfig(e.target.value)}
            placeholder="Units"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-blue/50 focus:border-neon-blue/50 transition-all"
          />
          <input
            value={resourceConfig}
            onChange={(e) => setResourceConfig(e.target.value)}
            placeholder="Resource (ex: energy)"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-blue/50 focus:border-neon-blue/50 transition-all"
          />
          <input
            value={goalConfig}
            onChange={(e) => setGoalConfig(e.target.value)}
            placeholder="Goal (ex: equilibrium)"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-blue/50 focus:border-neon-blue/50 transition-all"
          />
        </div>

        <Button
          onClick={async () => {
            await handleCommand(`balance units ${unitsConfig}`, "cfg1")
            await handleCommand(`balance resource ${resourceConfig}`, "cfg2")
            await handleCommand(`balance goal ${goalConfig}`, "cfg3")
            setConfigApplied(true)
          }}
          disabled={loading !== null}
          className="w-full bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30 transition-all duration-300"
        >
          {loading?.startsWith("cfg") ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : null}
          Aplicar Configuração
        </Button>

        {!isConfigured && (
          <div className="text-xs text-amber-400 border border-amber-500/30 bg-amber-500/10 p-3 rounded-lg">
            Configure Units, Resource e Goal antes de iniciar o balance.
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Button
          onClick={() => handleCommand("balance start", "start")}
          disabled={!configApplied || loading !== null}
          className="bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30 hover:text-green-300 hover:shadow-[0_0_15px_rgba(34,197,94,0.2)] transition-all duration-300"
        >
          {loading === "start" ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          Start
        </Button>
        <Button
          onClick={() => handleCommand("balance run", "run")}
          disabled={!configApplied || loading !== null}
          className="bg-neon-blue/20 border border-neon-blue/30 text-neon-blue hover:bg-neon-blue/30 hover:shadow-[0_0_15px_rgba(0,180,255,0.2)] transition-all duration-300"
        >
          {loading === "run" ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Run
        </Button>
        <Button
          onClick={() => handleCommand("balance stop", "stop")}
          disabled={!configApplied || loading !== null}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-red-300 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)] transition-all duration-300"
        >
          {loading === "stop" ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Square className="h-4 w-4 mr-2" />
          )}
          Stop
        </Button>
        <Button
          onClick={() => handleCommand("balance result", "result")}
          disabled={!configApplied || loading !== null}
          className="bg-neon-purple/20 border border-neon-purple/30 text-neon-purple hover:bg-neon-purple/30 hover:text-neon-purple hover:shadow-[0_0_15px_rgba(168,85,247,0.2)] transition-all duration-300"
        >
          {loading === "result" ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <FileText className="h-4 w-4 mr-2" />
          )}
          Result
        </Button>
      </div>

      {/* Last Result */}
      {lastResult && (
        <div className="rounded-lg border border-border/50 bg-secondary/30 p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <p className="text-xs font-medium text-muted-foreground mb-2">Último Resultado:</p>
          <p className="text-sm font-mono text-foreground whitespace-pre-line">{lastResult}</p>
        </div>
      )}
    </div>
  )
}
