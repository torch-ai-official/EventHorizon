"use client"

import { Database, Users, BarChart3 } from "lucide-react"
import { AppCard } from "./app-card"
import type { Unit } from "@/components/dashboard/units-panel"

interface DataAppProps {
  units: Unit[]
  onCreateUnit: () => void
}

export function DataApp({ units, onCreateUnit }: DataAppProps) {
  const activeUnits = units.filter(u => u.state === "active").length
  const idleUnits = units.filter(u => u.state === "idle").length
  const chargingUnits = units.filter(u => u.state === "charging").length
  const depletedUnits = units.filter(u => u.state === "depleted").length
  const avgEnergy = units.length > 0 
    ? Math.round(units.reduce((sum, u) => sum + u.energy, 0) / units.length)
    : 0

  return (
    <AppCard
      title="Dados"
      description="Estatísticas das unidades"
      icon={Database}
      variant="blue"
      actions={[
        {
          label: "Criar Unidade",
          onClick: onCreateUnit,
          variant: "blue"
        }
      ]}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-neon-blue" />
            <span className="text-sm text-muted-foreground">Total</span>
          </div>
          <span className="text-sm font-semibold text-foreground">{units.length}</span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="p-2 rounded-lg bg-green-500/10 border border-green-500/20">
            <p className="text-xs text-green-400">Ativos</p>
            <p className="text-lg font-bold text-green-400">{activeUnits}</p>
          </div>
          <div className="p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <p className="text-xs text-yellow-400">Ociosos</p>
            <p className="text-lg font-bold text-yellow-400">{idleUnits}</p>
          </div>
          <div className="p-2 rounded-lg bg-neon-cyan/10 border border-neon-cyan/20">
            <p className="text-xs text-neon-cyan">Carregando</p>
            <p className="text-lg font-bold text-neon-cyan">{chargingUnits}</p>
          </div>
          <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
            <p className="text-xs text-red-400">Esgotados</p>
            <p className="text-lg font-bold text-red-400">{depletedUnits}</p>
          </div>
        </div>

        <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-neon-purple" />
            <span className="text-sm text-muted-foreground">Energia Média</span>
          </div>
          <span className="text-sm font-semibold text-foreground">{avgEnergy}%</span>
        </div>
      </div>
    </AppCard>
  )
}
