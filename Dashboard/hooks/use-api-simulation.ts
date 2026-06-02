"use client"

import { useCallback, useEffect, useState, useRef } from "react"

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
    previsao_5s?: number    // ⭐ ADICIONADO
    previsao_15s?: number   // ⭐ ADICIONADO
    previsao_30s?: number   // ⭐ ADICIONADO
    previsao_60s?: number   // ⭐ ADICIONADO
    previsao_300s?: number
    previsao_900s?: number
    previsao_1800s?: number
    previsao_3600s?: number
    previsao_18000s?: number
    previsao_86400s?: number
    consenso_curto?: number
    consenso_medio?: number
    consenso_longo?: number
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
  previsao_5s?: number    // ⭐ ADICIONADO
  previsao_15s?: number   // ⭐ ADICIONADO
  previsao_30s?: number   // ⭐ ADICIONADO
  previsao_60s?: number   // ⭐ ADICIONADO
  previsao_300s?: number
  previsao_900s?: number
  previsao_1800s?: number
  previsao_3600s?: number
  previsao_18000s?: number
  previsao_86400s?: number
  consenso_curto?: number
  consenso_medio?: number
  consenso_longo?: number
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
    previsao_5s: (d as any).previsao_5s ?? 0,
    previsao_15s: (d as any).previsao_15s ?? 0,
    previsao_30s: (d as any).previsao_30s ?? 0,
    previsao_60s: (d as any).previsao_60s ?? 0,
   
    previsao_300s: (d as any).previsao_300s ?? 0,
    previsao_900s: (d as any).previsao_900s ?? 0,
    previsao_1800s: (d as any).previsao_1800s ?? 0,
    previsao_3600s: (d as any).previsao_3600s ?? 0,
    previsao_18000s: (d as any).previsao_18000s ?? 0,
    previsao_86400s: (d as any).previsao_86400s ?? 0,
    consenso_curto: (d as any).consenso_curto ?? 0,
    consenso_medio: (d as any).consenso_medio ?? 0,
    consenso_longo: (d as any).consenso_longo ?? 0,
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
  const [pollingPaused, setPollingPaused] = useState(false)
  const [initialFetchDone, setInitialFetchDone] = useState(false)

  const fetchStatus = useCallback(async () => {
    if (pollingPaused) return

    try {
      console.log("📡 Fetching status from:", `${API_BASE}/status`)
      const response = await fetch(`${API_BASE}/status`)
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data: ApiStatus = await response.json()
      console.log("✅ Data received:", data.dados?.length || 0, "units")

      // ⭐ LOG PARA VER OS VALORES CRUS DA API
      console.log("📦 DADOS CRUS DA API:", data.dados.map(d => ({
        symbol: d.symbol,
        previsao_5s: (d as any).previsao_5s,
        previsao_15s: (d as any).previsao_15s,
        previsao_30s: (d as any).previsao_30s,
        previsao_60s: (d as any).previsao_60s,
      })))

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
      
      setPulses(data.pulsos?.slice(0, MAX_ITEMS).map(mapApiPulse) || [])
      setTotalEnergy(data.energia_total || 0)
      setIsConnected(true)
      setError(null)
      setInitialFetchDone(true)
      
    } catch (err) {
      console.error("❌ Fetch error:", err)
      setIsConnected(false)
      setError("Falha ao conectar com a API")
    }
  }, [pollingPaused])

  const pausePolling = useCallback(() => {
    console.log("⏸️ Polling paused")
    setPollingPaused(true)
  }, [])

  const resumePolling = useCallback(() => {
    console.log("▶️ Polling resumed")
    setPollingPaused(false)
  }, [])

  const refreshUnits = useCallback(async () => {
    console.log("🔄 Manual refresh requested")
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
    console.log("🗑️ Clearing crypto units")
    setUnits(prevUnits => prevUnits.filter(u => !u.symbol && u.tipo !== "crypto"))
    setTimeout(() => {
      fetchStatus()
    }, 100)
  }, [fetchStatus])

  // ⭐ INITIAL FETCH - CRÍTICO!
  useEffect(() => {
    setMounted(true)
    console.log("🔧 useApiSimulation mounted, fetching initial data...")
    fetchStatus()
  }, [fetchStatus])

  // ⭐ Polling interval
  useEffect(() => {
    if (!mounted) return
    if (pollingPaused) {
      console.log("⏸️ Polling interval not started (paused)")
      return
    }
    
    console.log("🔄 Starting polling interval")
    const interval = setInterval(() => {
      fetchStatus()
    }, POLL_INTERVAL)
    
    return () => {
      console.log("🛑 Clearing polling interval")
      clearInterval(interval)
    }
  }, [mounted, fetchStatus, pollingPaused])

  return {
    mounted,
    isRunning,
    isConnected,
    error,
    units,
    pulses,
    totalEnergy,
    totalPulses: pulses.length,
    createUnit,
    sendPulse,
    togglePause,
    executeCommand,
    refreshUnits,
    pausePolling,
    resumePolling,
    clearUnits
  }
}