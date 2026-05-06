"use client"
 
import { useMemo } from "react"
import { Brain, Zap, Activity, Target } from "lucide-react"
import { SignalCard } from "@/components/dashboard/signal-card"
import { SignalsPanel } from "@/components/dashboard/signals-panel"
import { ActivityFeed } from "@/components/dashboard/activity-feed"
import { SystemHealth } from "@/components/dashboard/system-health"
import type { EnergyDataPoint } from "@/components/dashboard/system-health"
 
interface Unit {
  id: string
  energia?: number
  symbol?: string
  price?: number
  delta?: number
  tipo?: string
  previsao?: number
  candles?: any[]
  accuracy?: number
}
 
interface Pulse {
  id: string
  from: string
  to: string
  energy: number
  timestamp: Date
}
 
interface DashboardTabProps {
  isRunning: boolean
  units: Unit[]
  pulses: Pulse[]
  chartData: EnergyDataPoint[]
  totalEnergy: number
  totalPulses: number
  onCreateUnit: () => void
  onSendPulse: () => void
  onTogglePause: () => void
}
 
export function DashboardTab({
  isRunning,
  units,
  pulses,
  chartData,
  totalEnergy,
  totalPulses,
  onTogglePause,
}: DashboardTabProps) {
 
  const cryptos = useMemo(
    () => units.filter(u => u.tipo === "crypto" && u.symbol),
    [units]
  )
 
  // Sinal dominante
  const dominantSignal = useMemo(() => {
    if (cryptos.length === 0) return null
    return [...cryptos].sort((a, b) => Math.abs(b.previsao ?? 0) - Math.abs(a.previsao ?? 0))[0]
  }, [cryptos])
 
  const signalLabel = useMemo(() => {
    const p = dominantSignal?.previsao ?? 0
    if (p > 2) return { text: "Compra forte", accent: "green" as const }
    if (p > 0.5) return { text: "Compra", accent: "green" as const }
    if (p < -2) return { text: "Venda forte", accent: "red" as const }
    if (p < -0.5) return { text: "Venda", accent: "red" as const }
    return { text: "Neutro", accent: "amber" as const }
  }, [dominantSignal])
 
  // Precisão média
  const avgAccuracy = useMemo(() => {
    const acc = cryptos.map(c => (c as any).accuracy).filter(Boolean)
    if (acc.length === 0) return undefined
    return Math.round(acc.reduce((a: number, b: number) => a + b, 0) / acc.length * 100)
  }, [cryptos])
 
  // Confiança do sinal dominante
  const dominantConfidence = dominantSignal
    ? Math.round(Math.min(100, Math.max(0, (dominantSignal.energia ?? 0) * 10)))
    : 0
 
  const positiveCount = cryptos.filter(c => (c.previsao ?? 0) > 0.5).length
  const negativeCount = cryptos.filter(c => (c.previsao ?? 0) < -0.5).length
 
  return (
    <div className="space-y-4">
 
      {/* ── 4 métricas topo ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SignalCard
          label="Sinal dominante"
          value={dominantSignal ? dominantSignal.symbol?.replace("USDT", "") ?? "—" : "—"}
          sub={signalLabel.text}
          icon={Brain}
          accent={signalLabel.accent}
        />
        <SignalCard
          label="Confiança"
          value={`${dominantConfidence}%`}
          sub={`${cryptos.length} ativos monitorados`}
          icon={Target}
          accent="blue"
          trend={dominantConfidence > 60 ? "up" : dominantConfidence > 40 ? "neutral" : "down"}
          trendText={dominantConfidence > 60 ? "Alta confiança" : "Baixa confiança"}
        />
        <SignalCard
          label="Em alta"
          value={positiveCount}
          sub={`${negativeCount} em baixa`}
          icon={Activity}
          accent={positiveCount > negativeCount ? "green" : "red"}
        />
        <SignalCard
          label="Energia total"
          value={Math.round(totalEnergy).toLocaleString()}
          sub={`${totalPulses} pulsos ativos`}
          icon={Zap}
          accent="purple"
        />
      </div>
 
      {/* ── Linha principal ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sinais — ocupa 2 colunas */}
        <div className="lg:col-span-2">
          <SignalsPanel units={units} />
        </div>
 
        {/* Saúde do sistema */}
        <div>
          <SystemHealth
            totalEnergy={totalEnergy}
            totalAgents={units.length}
            totalPulses={totalPulses}
            chartData={chartData}
            isRunning={isRunning}
            cryptoStatus={cryptos.length > 0 ? "active" : "idle"}
            accuracy={avgAccuracy}
          />
        </div>
      </div>
 
      {/* ── Feed de atividade ─────────────────────────────────────────── */}
      <ActivityFeed pulses={pulses} />
 
    </div>
  )
}