"use client"

import { useState, useEffect, useRef } from "react"
import { Activity, Zap, ArrowRightLeft, Gauge, Play, Square, RefreshCw, FileText, Loader2, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from "recharts"

interface Pulse {
  id: string
  from: string
  to: string
  energy: number
  timestamp: Date
}

interface FlowAppProps {
  pulses: Pulse[]
  totalEnergy: number
  executeCommand: (command: string) => Promise<string>
}

export function FlowApp({
  pulses,
  totalEnergy,
  executeCommand
}: FlowAppProps) {
  const [loading, setLoading] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)

  const [source, setSource] = useState("")
  const [target, setTarget] = useState("")
  const [range, setRange] = useState("220")
  
  // State for running indicator
  const [isRunning, setIsRunning] = useState(false)
  
  // History for chart
  const [history, setHistory] = useState<{ time: string; pulses: number; energy: number }[]>([])
  const lastPulseCount = useRef(0)

  const isConfigured = source !== "" && target !== ""

  const totalPulses = pulses.length
  const energyInTransit = pulses.slice(-10).reduce((acc, p) => acc + (p.energy || 0), 0)
  const flowRate = pulses.length > 0 
    ? Math.round(pulses.slice(-10).reduce((acc, p) => acc + (p.energy || 0), 0) / Math.max(1, pulses.slice(-10).length))
    : 0

  // Update history when pulses change
  useEffect(() => {
    if (pulses.length === 0) return
    if (pulses.length === lastPulseCount.current) return
    
    lastPulseCount.current = pulses.length
    
    const now = new Date().toLocaleTimeString("pt-BR", { 
      hour: "2-digit", 
      minute: "2-digit",
      second: "2-digit"
    })
    
    setHistory(prev => {
      const newHistory = [...prev, { 
        time: now, 
        pulses: totalPulses, 
        energy: energyInTransit 
      }]
      return newHistory.slice(-20) // Keep last 20 points
    })
  }, [pulses, totalPulses, energyInTransit])

  // Alert on page leave if running
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isRunning) {
        e.preventDefault()
        e.returnValue = "O Flow ainda está em execução. Tem certeza que deseja sair?"
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

  // Get recent pulses data for mini bar chart
  const recentPulsesData = pulses.slice(-8).map((p, i) => ({
    name: i.toString(),
    energy: p.energy || 0
  }))

  return (
    <div className="space-y-6">
      {/* Header with Running Indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-neon-cyan" />
          <span className="text-sm font-medium text-foreground">Fluxo de Energia</span>
        </div>
        {/* Running Indicator */}
        {isRunning && (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30 animate-pulse">
            <Activity className="h-3 w-3 animate-pulse" />
            Running
          </span>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-4">
        {/* Total Pulses */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-neon-cyan/50 hover:shadow-[0_0_15px_rgba(0,255,255,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-neon-cyan/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <ArrowRightLeft className="h-4 w-4 text-neon-cyan" />
              <span className="text-xs font-medium text-muted-foreground">Total Pulsos</span>
            </div>
            <p className="text-2xl font-bold tracking-tight text-foreground">
              {totalPulses}
            </p>
          </div>
        </div>

        {/* Energy in Transit */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-neon-blue/50 hover:shadow-[0_0_15px_rgba(0,180,255,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-neon-blue/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-neon-blue" />
              <span className="text-xs font-medium text-muted-foreground">Em Trânsito</span>
            </div>
            <p className="text-2xl font-bold tracking-tight text-neon-blue">
              {energyInTransit}
            </p>
          </div>
        </div>

        {/* Flow Rate */}
        <div className="relative overflow-hidden rounded-lg border border-border/50 bg-secondary/30 p-4 transition-all duration-300 hover:border-neon-purple/50 hover:shadow-[0_0_15px_rgba(168,85,247,0.1)]">
          <div className="absolute inset-0 bg-gradient-to-br from-neon-purple/5 to-transparent" />
          <div className="relative space-y-2">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-neon-purple" />
              <span className="text-xs font-medium text-muted-foreground">Taxa Média</span>
            </div>
            <p className={cn(
              "text-2xl font-bold tracking-tight transition-colors duration-300",
              flowRate > 50 ? "text-green-400" : flowRate > 20 ? "text-amber-400" : "text-neon-purple"
            )}>
              {flowRate}
            </p>
          </div>
        </div>
      </div>

      {/* Flow Evolution Chart */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Evolução do Fluxo</span>
          <span className="text-muted-foreground">{history.length} pontos</span>
        </div>
        <div className="h-36 rounded-lg border border-border/50 bg-secondary/20 p-3">
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
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
                <Line 
                  type="monotone" 
                  dataKey="pulses" 
                  stroke="hsl(var(--neon-cyan))" 
                  strokeWidth={2}
                  dot={false}
                  name="Pulsos"
                />
                <Line 
                  type="monotone" 
                  dataKey="energy" 
                  stroke="hsl(var(--neon-purple))" 
                  strokeWidth={2}
                  dot={false}
                  name="Energia"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              Aguardando dados para o gráfico...
            </div>
          )}
        </div>
      </div>

      {/* Recent Pulses with Mini Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Pulses List */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Pulsos Recentes</p>
          <div className="h-32 overflow-y-auto rounded-lg border border-border/50 bg-secondary/20 p-3 space-y-2">
            {pulses.slice(-5).reverse().map((pulse, index) => (
              <div 
                key={pulse.id} 
                className={cn(
                  "flex items-center justify-between text-xs transition-all duration-300",
                  index === 0 && "animate-in fade-in slide-in-from-top-2"
                )}
              >
                <span className="font-mono text-muted-foreground">
                  {pulse.from} → {pulse.to}
                </span>
                <span className={cn(
                  "font-medium",
                  (pulse.energy || 0) > 30 ? "text-green-400" : "text-neon-cyan"
                )}>
                  +{pulse.energy || 0}
                </span>
              </div>
            ))}
            {pulses.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                Nenhum pulso registrado
              </p>
            )}
          </div>
        </div>

        {/* Mini Bar Chart */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Energia por Pulso</p>
          <div className="h-32 rounded-lg border border-border/50 bg-secondary/20 p-3">
            {recentPulsesData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={recentPulsesData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                  <XAxis hide />
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
                  <Bar 
                    dataKey="energy" 
                    fill="hsl(var(--neon-cyan))"
                    radius={[4, 4, 0, 0]}
                    name="Energia"
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                Sem dados
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-muted-foreground">Configuração</p>
        <div className="grid grid-cols-3 gap-3">
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Source ID"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-cyan/50 focus:border-neon-cyan/50 transition-all"
          />
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="Target ID"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-cyan/50 focus:border-neon-cyan/50 transition-all"
          />
          <input
            value={range}
            onChange={(e) => setRange(e.target.value)}
            placeholder="Range"
            className="bg-secondary/30 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neon-cyan/50 focus:border-neon-cyan/50 transition-all"
          />
        </div>

        <Button
          onClick={async () => {
            await handleCommand(`flow source ${source}`, "cfg1")
            await handleCommand(`flow target ${target}`, "cfg2")
            await handleCommand(`flow range ${range}`, "cfg3")
          }}
          disabled={loading !== null}
          className="w-full bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30 transition-all duration-300"
        >
          {loading?.startsWith("cfg") ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : null}
          Aplicar Configuração
        </Button>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Button
          onClick={() => handleCommand("flow start", "start")}
          disabled={!isConfigured || loading !== null}
          className="bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30 hover:shadow-[0_0_15px_rgba(34,197,94,0.2)] transition-all duration-300"
        >
          {loading === "start" ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <Play className="h-4 w-4 mr-2" />}
          Start
        </Button>

        <Button
          onClick={() => handleCommand("flow run", "run")}
          disabled={!isConfigured || loading !== null}
          className="bg-neon-cyan/20 border border-neon-cyan/30 text-neon-cyan hover:bg-neon-cyan/30 hover:shadow-[0_0_15px_rgba(0,255,255,0.2)] transition-all duration-300"
        >
          {loading === "run" ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          Run
        </Button>

        <Button
          onClick={() => handleCommand("flow stop", "stop")}
          disabled={!isConfigured || loading !== null}
          className="bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)] transition-all duration-300"
        >
          {loading === "stop" ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <Square className="h-4 w-4 mr-2" />}
          Stop
        </Button>

        <Button
          onClick={() => handleCommand("flow result", "result")}
          disabled={!isConfigured || loading !== null}
          className="bg-neon-purple/20 border border-neon-purple/30 text-neon-purple hover:bg-neon-purple/30 hover:shadow-[0_0_15px_rgba(168,85,247,0.2)] transition-all duration-300"
        >
          {loading === "result" ? <Loader2 className="animate-spin h-4 w-4 mr-2" /> : <FileText className="h-4 w-4 mr-2" />}
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
