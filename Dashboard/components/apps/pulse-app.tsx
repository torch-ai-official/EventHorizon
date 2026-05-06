"use client"

import { Activity, Zap, ArrowRightLeft } from "lucide-react"
import { AppCard } from "./app-card"
import type { Pulse } from "@/components/dashboard/pulses-panel"

interface PulseAppProps {
  pulses: Pulse[]
  onSendPulse: () => void
}

export function PulseApp({ pulses, onSendPulse }: PulseAppProps) {
  const totalEnergyTransferred = pulses.reduce((sum, p) => sum + p.energy, 0)
  const avgEnergyPerPulse = pulses.length > 0 
    ? Math.round(totalEnergyTransferred / pulses.length)
    : 0
  const recentPulses = pulses.slice(0, 3)

  return (
    <AppCard
      title="Pulsos"
      description="Gerenciamento de transferências"
      icon={Activity}
      variant="purple"
      actions={[
        {
          label: "Enviar Pulso",
          onClick: onSendPulse,
          variant: "purple"
        }
      ]}
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30">
            <Zap className="h-5 w-5 text-neon-purple" />
            <div>
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-sm font-semibold text-foreground">{pulses.length}</p>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30">
            <ArrowRightLeft className="h-5 w-5 text-neon-cyan" />
            <div>
              <p className="text-xs text-muted-foreground">Transferido</p>
              <p className="text-sm font-semibold text-foreground">{totalEnergyTransferred}</p>
            </div>
          </div>
        </div>

        <div className="p-3 rounded-lg bg-secondary/30">
          <p className="text-xs text-muted-foreground mb-2">Média por pulso</p>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-neon-purple">{avgEnergyPerPulse}</span>
            <span className="text-sm text-muted-foreground">E</span>
          </div>
        </div>

        {recentPulses.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">Pulsos Recentes</p>
            {recentPulses.map((pulse) => (
              <div 
                key={pulse.id}
                className="flex items-center justify-between p-2 rounded-lg bg-neon-purple/5 border border-neon-purple/10"
              >
                <span className="text-xs font-mono text-muted-foreground">
                  {pulse.from} → {pulse.to}
                </span>
                <span className="text-xs font-semibold text-neon-purple">+{pulse.energy}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppCard>
  )
}
