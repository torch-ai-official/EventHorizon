// components/tabs/dashboard-tab.tsx
"use client"

import { cn } from "@/lib/utils"
import { useMemo } from "react"
import { 
  TrendingUp, TrendingDown, Activity, Zap, 
  Award, Clock, Brain, Target, BarChart3 
} from "lucide-react"
import { SignalCard } from "@/components/dashboard/signal-card"
import { SignalsPanel } from "@/components/dashboard/signals-panel"
import { TraderMetrics } from "@/components/dashboard/TraderMetrics"
import { useCryptoStats } from "@/hooks/useCryptoStats"  // ⭐ NOVO

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
  n_acertos?: number
  n_erros?: number
}

interface DashboardTabProps {
  isRunning: boolean
  units: Unit[]
  pulses: any[]
  totalEnergy: number
  totalPulses: number
  onCreateUnit: () => void
  onSendPulse: () => void
  onTogglePause: () => void
}

export function DashboardTab({
  isRunning,
  units,
  totalEnergy,
  totalPulses,
  onTogglePause,
}: DashboardTabProps) {
  
  // ⭐ Agora usando dados reais das mentes PyTorch
  const { stats, loading } = useCryptoStats()
  
  // Filtra apenas moedas crypto
  const cryptos = useMemo(
    () => units.filter(u => u.tipo === "crypto" && u.symbol),
    [units]
  )

  // Sinal dominante (maior força de previsão)
  const dominantSignal = useMemo(() => {
    if (cryptos.length === 0) return null
    return [...cryptos].sort((a, b) => Math.abs(b.previsao ?? 0) - Math.abs(a.previsao ?? 0))[0]
  }, [cryptos])

  // Texto do sinal dominante
  const signalLabel = useMemo(() => {
    const p = dominantSignal?.previsao ?? 0
    if (p > 2) return { text: "COMPRA FORTE", accent: "green" as const, icon: TrendingUp }
    if (p > 0.5) return { text: "COMPRA", accent: "green" as const, icon: TrendingUp }
    if (p < -2) return { text: "VENDA FORTE", accent: "red" as const, icon: TrendingDown }
    if (p < -0.5) return { text: "VENDA", accent: "red" as const, icon: TrendingDown }
    return { text: "AGUARDAR", accent: "amber" as const, icon: Activity }
  }, [dominantSignal])

  // Confiança do sinal dominante
  const dominantConfidence = useMemo(() => {
    if (!dominantSignal) return 0
    return Math.round(Math.min(100, Math.max(0, (dominantSignal.energia ?? 0) * 12)))
  }, [dominantSignal])

  // Estatísticas das moedas
  const positiveCount = cryptos.filter(c => (c.previsao ?? 0) > 0.5).length
  const negativeCount = cryptos.filter(c => (c.previsao ?? 0) < -0.5).length
  const neutralCount = cryptos.length - positiveCount - negativeCount

  // ⭐ Acurácia média vinda do SQL/mentes PyTorch
  const avgAccuracy = stats.acuracia_geral || 0

  // Performance por moeda (vem das mentes PyTorch via API)
  const performanceByCoin = stats.performance_moedas || []
  const bestCoin = performanceByCoin[0]
  
  // Melhores horários (vem do SQL)
  const melhoresHorarios = stats.melhores_horarios || []
  const pioresHorarios = stats.piores_horarios || []
  
  // Total de trades
  const totalTrades = stats.total_previsoes || 0

  return (
    <div className="space-y-6">
      {/* LINHA 1: CARDS PRINCIPAIS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Sinal Dominante */}
        <SignalCard
          label="SINAL DO MOMENTO"
          value={dominantSignal ? dominantSignal.symbol?.replace("USDT", "") ?? "-" : "-"}
          sub={signalLabel.text}
          icon={signalLabel.icon || Brain}
          accent={signalLabel.accent}
        />

        {/* Card 2: Confianca */}
        <SignalCard
          label="CONFIANCA IA"
          value={`${dominantConfidence}%`}
          sub={`${cryptos.length} moedas monitoradas`}
          icon={Target}
          accent="blue"
          trend={dominantConfidence > 60 ? "up" : dominantConfidence > 40 ? "neutral" : "down"}
          trendText={dominantConfidence > 60 ? "Alta confianca" : dominantConfidence > 40 ? "Media" : "Baixa confianca"}
        />

        {/* Card 3: Acuracia Geral (das mentes PyTorch) */}
        <SignalCard
          label="ACURACIA GERAL"
          value={`${avgAccuracy}%`}
          sub={`Baseado em ${totalTrades} analises`}
          icon={BarChart3}
          accent={avgAccuracy > 55 ? "green" : avgAccuracy > 45 ? "amber" : "red"}
        />

        {/* Card 4: Posicao do Mercado */}
        <SignalCard
          label="MERCADO"
          value={positiveCount > negativeCount ? "ALTA" : negativeCount > positiveCount ? "BAIXA" : "LATERAL"}
          sub={`${positiveCount} sobe | ${neutralCount} lateral | ${negativeCount} desce`}
          icon={Activity}
          accent={positiveCount > negativeCount ? "green" : negativeCount > positiveCount ? "red" : "amber"}
        />
      </div>

      {/* LINHA 2: SINAIS + METRICAS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sinais */}
        <div className="lg:col-span-2">
          <SignalsPanel units={cryptos} />
        </div>

        {/* Metricas */}
        <div>
          <TraderMetrics 
            accuracy={avgAccuracy}
            bestTime={melhoresHorarios[0]?.hora || "14:00"}
            worstTime={pioresHorarios[0]?.hora || "12:00"}
            totalTrades={totalTrades}
            winRate={avgAccuracy}
          />
        </div>
      </div>

      {/* LINHA 3: PERFORMANCE + MELHORES HORARIOS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance por Moeda (das mentes PyTorch) */}
        <div className="rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Award className="h-4 w-4 text-yellow-500" />
              PERFORMANCE POR MOEDA
            </h3>
            {bestCoin && (
              <span className="text-[10px] text-green-400">
                Melhor: {bestCoin.symbol.replace("USDT", "")} ({Math.round(bestCoin.acuracia)}%)
              </span>
            )}
          </div>
          <div className="space-y-3">
            {performanceByCoin.slice(0, 5).map((coin) => (
              <div key={coin.symbol} className="flex items-center justify-between p-2 rounded-lg hover:bg-secondary/30 transition-colors">
                <div className="flex items-center gap-3 w-24">
                  <span className="font-mono text-sm font-medium text-foreground">
                    {coin.symbol.replace("USDT", "")}
                  </span>
                </div>
                <div className="flex-1 mx-4">
                  <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                    <div 
                      className={cn(
                        "h-full rounded-full transition-all duration-500",
                        coin.acuracia >= 55 ? "bg-green-400" :
                        coin.acuracia >= 45 ? "bg-yellow-400" : "bg-red-400"
                      )}
                      style={{ width: `${coin.acuracia}%` }} 
                    />
                  </div>
                </div>
                <div className="text-right w-16">
                  <span className="text-sm font-bold tabular-nums">
                    {Math.round(coin.acuracia)}%
                  </span>
                  <div className="text-[10px] text-muted-foreground">
                    {coin.acertos}/{coin.total}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {performanceByCoin.length === 0 && !loading && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Nenhuma moeda carregada. Va para a aba "Crypto Trading" e carregue suas moedas.
            </div>
          )}
          {loading && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Carregando dados das IAs...
            </div>
          )}
        </div>

        {/* Melhores Horarios para Trade */}
        <div className="rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm p-5">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Clock className="h-4 w-4 text-cyan-400" />
            MELHORES HORARIOS PARA TRADE
          </h3>
          <div className="space-y-4">
            <div className="space-y-2">
              {melhoresHorarios.slice(0, 3).map((horario, index) => (
                <div key={horario.hora} className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold w-8">
                      {index === 0 ? "1o" : index === 1 ? "2o" : "3o"}
                    </span>
                    <span className="font-mono font-bold">{horario.hora}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-1.5 bg-secondary rounded-full overflow-hidden">
                      <div 
                        className={cn(
                          "h-full rounded-full",
                          horario.acuracia >= 60 ? "bg-green-400" : 
                          horario.acuracia >= 50 ? "bg-yellow-400" : "bg-red-400"
                        )}
                        style={{ width: `${Math.min(100, horario.acuracia)}%` }} 
                      />
                    </div>
                    <span className={cn(
                      "text-sm font-bold w-12 text-right",
                      horario.acuracia >= 60 ? "text-green-400" : 
                      horario.acuracia >= 50 ? "text-yellow-400" : "text-red-400"
                    )}>
                      {Math.round(horario.acuracia)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            
            {pioresHorarios.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <p className="text-xs text-red-400 flex items-center gap-2">
                  <span>ATENCAO</span> 
                  <span>Evite trades as {pioresHorarios[0]?.hora || "12:00"} — acuracia de apenas {Math.round(pioresHorarios[0]?.acuracia || 0)}%</span>
                </p>
              </div>
            )}

            <div className="pt-2 text-center">
              <p className="text-[10px] text-muted-foreground">
                Baseado em {totalTrades} previsoes registradas
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* LINHA 4: DICA DO DIA */}
      {bestCoin && bestCoin.acuracia > 55 && (
        <div className="rounded-xl bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-green-500/20">
              <TrendingUp className="h-4 w-4 text-green-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-green-400">DICA DO DIA</p>
              <p className="text-xs text-muted-foreground">
                {bestCoin.symbol.replace("USDT", "")} esta com {Math.round(bestCoin.acuracia)}% de acuracia. 
                Este e o momento com maior confiabilidade para operar.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}