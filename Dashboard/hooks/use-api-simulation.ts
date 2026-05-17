"use client"

import { useCallback, useEffect, useState, useRef } from "react"
import type { EnergyDataPoint } from "@/components/dashboard/system-health"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const MAX_ITEMS = 50
const POLL_INTERVAL = 2000

interface ApiStatus {
  energia_total: number
  dados: Array<{
    id: string
    energia: number
    estado: string
    symbol?: string
    price?: number
    delta?: number
    tipo?: string
    previsao?: number
    candles?: any[]
    accuracy?: number
  }>
  pulsos: Array<{
    id: string
    de: string
    para: string
    energia: number
    timestamp: string
  }>
}

export interface Unit {
  id: string
  energia?: number
  state: "active" | "idle" | "charging" | "depleted"
  symbol?: string
  price?: number
  delta?: number
  tipo?: string
  previsao?: number
  candles?: any[]
  accuracy?: number
}

export interface Pulse {
  id: string
  from: string
  to: string
  energy: number
  timestamp: Date
}

function mapApiUnitState(estado: string): Unit["state"] {
  const map: Record<string, Unit["state"]> = {
    ativo: "active", ocioso: "idle", carregando: "charging", esgotado: "depleted",
    active: "active", idle: "idle", charging: "charging", depleted: "depleted"
  }
  return map[estado?.toLowerCase?.()] ?? "idle"
}

function mapApiUnit(d: ApiStatus["dados"][0]): Unit {
  return {
    id: d.id,
    energia: d.energia,
    state: mapApiUnitState(d.estado),
    symbol: d.symbol,
    price: d.price,
    delta: d.delta,
    tipo: d.tipo,
    previsao: d.previsao ?? 0,
    candles: d.candles ?? [],
    accuracy: d.accuracy,
  }
}

function mapApiPulse(p: ApiStatus["pulsos"][0]): Pulse {
  return {
    id: p.id,
    from: p.de,
    to: p.para,
    energy: p.energia,
    timestamp: new Date(p.timestamp),
  }
}

export function useApiSimulation() {
  const [mounted, setMounted] = useState(false)
  const [isRunning, setIsRunning] = useState(true)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [units, setUnits] = useState<Unit[]>([])
  const [pulses, setPulses] = useState<Pulse[]>([])
  const [totalEnergy, setTotalEnergy] = useState(0)
  const [chartData, setChartData] = useState<EnergyDataPoint[]>([])

  const chartHistoryRef = useRef<EnergyDataPoint[]>([])

  // ⭐ Controle do polling
  const [pollingPaused, setPollingPaused] = useState(false)

  const fetchStatus = useCallback(async () => {
    // ⭐ Se o polling está pausado, não faz nada
    if (pollingPaused) return

    try {
      const response = await fetch(`${API_BASE}/status`)
      if (!response.ok) throw new Error("API não disponível")

      const data: ApiStatus = await response.json()

      setUnits(prevUnits => {
        const novos = data.dados.map(mapApiUnit)
        const mapa = new Map(prevUnits.map(u => [u.id, u]))

        for (const novo of novos) {
          mapa.set(novo.id, {
            ...mapa.get(novo.id),
            ...novo,
            candles: novo.candles?.length ? novo.candles : mapa.get(novo.id)?.candles
          })
        }
        return Array.from(mapa.values())
      })
      
      setPulses(data.pulsos.slice(0, MAX_ITEMS).map(mapApiPulse))
      setTotalEnergy(data.energia_total)
      setIsConnected(true)
      setError(null)

      const newPoint: EnergyDataPoint = {
        time: new Date().toLocaleTimeString("pt-BR", {
          hour: "2-digit", minute: "2-digit", second: "2-digit"
        }),
        energy: data.energia_total,
        pulses: data.pulsos.length,
      }

      chartHistoryRef.current = [...chartHistoryRef.current.slice(-19), newPoint]
      setChartData([...chartHistoryRef.current])
    } catch {
      setIsConnected(false)
      setError("Falha ao conectar com a API")
    }
  }, [pollingPaused])

  // ⭐ Funções para controlar o polling
  const pausePolling = useCallback(() => {
    setPollingPaused(true)
  }, [])

  const resumePolling = useCallback(() => {
    setPollingPaused(false)
  }, [])

  // ⭐ Força refresh manual dos dados
  const refreshUnits = useCallback(async () => {
    // Temporariamente desativa a pausa para fazer o refresh
    const wasPaused = pollingPaused
    if (wasPaused) {
      setPollingPaused(false)
      await fetchStatus()
      setPollingPaused(true)
    } else {
      await fetchStatus()
    }
  }, [fetchStatus, pollingPaused])

  const createUnit = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/criar`, { method: "POST" })
      await fetchStatus()
    } catch (err) {
      console.error("Erro ao criar unidade:", err)
    }
  }, [fetchStatus])

  const sendPulse = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/pulso`, { method: "POST" })
      await fetchStatus()
    } catch (err) {
      console.error("Erro ao enviar pulso:", err)
    }
  }, [fetchStatus])

  const togglePause = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/toggle`, { method: "POST" })
      setIsRunning(prev => !prev)
    } catch (err) {
      console.error("Erro ao alternar pausa:", err)
    }
  }, [])

  const executeCommand = useCallback(async (command: string): Promise<string> => {
    try {
      const response = await fetch(`${API_BASE}/comando`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comando: command }),
      })
      if (!response.ok) return `Erro: ${response.status} ${response.statusText}`
      const data = await response.json()
      return data.prompt + " " + data.resultado || data.message || JSON.stringify(data, null, 2)
    } catch {
      return `Erro de conexão — verifique se a API está rodando em ${API_BASE}`
    }
  }, [])

  const clearUnits = useCallback(() => {
  // Remove todas as unidades crypto do estado local
  setUnits(prevUnits => prevUnits.filter(u => !u.symbol && u.tipo !== "crypto"))
  }, [])

  useEffect(() => {
    setMounted(true)
    fetchStatus()
  }, [fetchStatus])

  // ⭐ Polling modificado para respeitar o pause
  useEffect(() => {
    if (!mounted) return
    if (pollingPaused) return // Não inicia intervalo se estiver pausado
    
    const interval = setInterval(fetchStatus, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [mounted, fetchStatus, pollingPaused])

  return {
    mounted,
    isRunning,
    isConnected,
    error,
    units,
    pulses,
    chartData,
    totalEnergy,
    totalPulses: pulses.length,
    createUnit,
    sendPulse,
    togglePause,
    executeCommand,
    refreshUnits,
    pausePolling,   // ⭐ NOVO - pausa o polling
    resumePolling,  // ⭐ NOVO - retoma o polling
    clearUnits      // ⭐ NOVO - limpa as unidades crypto do estado
  }
}