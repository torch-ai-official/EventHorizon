// hooks/use-dashboard-realtime.ts
"use client"

import { useState, useEffect } from "react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
import { API_BASE_URL } from '@/lib/api';
interface MoedaRealtime {
  symbol: string
  price: number
  delta: number
  energia: number
  rsi: number
  regime: string
  previsao_5s: number
  previsao_60s: number
  previsao_300s: number
  previsao_900s: number
  consenso_curto: number
  consenso_medio: number
  consenso_longo: number
  geracoes: number
  acc_treino: number
  acc_real_5s: number
  acc_real_60s: number
  acc_real_300s: number
  total_verificacoes: number
}

interface DashboardRealtime {
  moedas: MoedaRealtime[]
  total_moedas: number
  melhor_moeda: MoedaRealtime | null
  mercado: {
    bullish: number
    bearish: number
    neutral: number
    tendencia: string
  }
  total_verificacoes: number
}

export function useDashboardRealtime() {
  const [data, setData] = useState<DashboardRealtime | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/dashboard/realtime`)
        const json = await response.json()
        setData(json)
      } catch (e) {
        console.error("Dashboard realtime error:", e)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 3000) // Atualiza a cada 3s
    return () => clearInterval(interval)
  }, [])

  return { data, loading }
}