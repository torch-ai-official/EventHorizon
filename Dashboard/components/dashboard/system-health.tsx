"use client"
 
import { cn } from "@/lib/utils"
import { TrendingUp, CheckCircle, AlertCircle, Clock } from "lucide-react"
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts"
 
export interface EnergyDataPoint {
  time: string
  energy: number
  pulses: number
}
 
interface SystemHealthProps {
  totalEnergy: number
  totalAgents: number
  totalPulses: number
  chartData: EnergyDataPoint[]
  isRunning: boolean
  balanceStatus?: "stable" | "running" | "idle"
  flowStatus?: "found" | "running" | "idle"
  cryptoStatus?: "active" | "idle"
  accuracy?: number
}
 
const statusConfig = {
  stable: { label: "Estável", color: "text-emerald-400", icon: CheckCircle },
  running: { label: "Rodando", color: "text-amber-400", icon: Clock },
  found: { label: "Rota ok", color: "text-emerald-400", icon: CheckCircle },
  active: { label: "Ativo", color: "text-emerald-400", icon: CheckCircle },
  idle: { label: "Inativo", color: "text-muted-foreground", icon: AlertCircle },
}
 
export function SystemHealth({
  totalEnergy,
  totalAgents,
  totalPulses,
  chartData,
  isRunning,
  balanceStatus = "idle",
  flowStatus = "idle",
  cryptoStatus = "idle",
  accuracy,
}: SystemHealthProps) {
 
  const bCfg = statusConfig[balanceStatus]
  const fCfg = statusConfig[flowStatus]
  const cCfg = statusConfig[cryptoStatus]
  const BalanceIcon = bCfg.icon
  const FlowIcon = fCfg.icon
  const CryptoIcon = cCfg.icon
 
  return (
    <div className="rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Saúde do sistema</h3>
        <div className={cn(
          "flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full",
          isRunning
            ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
            : "text-amber-400 bg-amber-500/10 border border-amber-500/20"
        )}>
          <span className={cn(
            "h-1.5 w-1.5 rounded-full",
            isRunning ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
          )} />
          {isRunning ? "Rodando" : "Pausado"}
        </div>
      </div>
 
      {/* Métricas principais */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Energia", value: Math.round(totalEnergy).toLocaleString() },
          { label: "Agentes", value: totalAgents },
          { label: "Pulsos", value: totalPulses },
        ].map(({ label, value }) => (
          <div key={label} className="bg-secondary/30 rounded-lg p-3 text-center">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
            <p className="text-lg font-semibold text-foreground">{value}</p>
          </div>
        ))}
      </div>
 
      {/* Mini chart */}
      {chartData.length > 2 && (
        <div className="h-16">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="ehGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis domain={["auto", "auto"]} hide />
              <Tooltip
                contentStyle={{
                  background: "var(--color-background-secondary, #1a1a2e)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "8px",
                  fontSize: "11px"
                }}
                itemStyle={{ color: "#10b981" }}
                labelStyle={{ color: "#888" }}
                formatter={(v: number) => [Math.round(v), "Energia"]}
              />
              <Area
                type="monotone"
                dataKey="energy"
                stroke="#10b981"
                strokeWidth={1.5}
                fill="url(#ehGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
 
      {/* Status dos apps */}
      <div className="space-y-1.5 border-t border-border/30 pt-3">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Módulos</p>
        {[
          { label: "Balance", cfg: bCfg, Icon: BalanceIcon },
          { label: "Flow", cfg: fCfg, Icon: FlowIcon },
          { label: "Crypto", cfg: cCfg, Icon: CryptoIcon },
        ].map(({ label, cfg, Icon }) => (
          <div key={label} className="flex items-center justify-between py-1">
            <span className="text-xs text-muted-foreground">{label}</span>
            <div className={cn("flex items-center gap-1 text-xs font-medium", cfg.color)}>
              <Icon className="h-3 w-3" />
              <span>{cfg.label}</span>
            </div>
          </div>
        ))}
        {accuracy !== undefined && (
          <div className="flex items-center justify-between py-1 border-t border-border/20 mt-1">
            <span className="text-xs text-muted-foreground">Precisão IA</span>
            <span className={cn(
              "text-xs font-semibold",
              accuracy > 60 ? "text-emerald-400" : accuracy > 45 ? "text-amber-400" : "text-red-400"
            )}>
              {accuracy}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}