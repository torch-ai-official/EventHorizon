// components/tabs/dashboard-tab.tsx
"use client"

import { useState, useEffect } from "react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export function DashboardTab() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(`${API_BASE}/dashboard/realtime`)
        const json = await response.json()
        setData(json)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="text-center py-10 text-sm text-muted-foreground">Carregando...</div>
  if (!data || data.moedas.length === 0) return <div className="text-center py-10 text-sm text-muted-foreground">Nenhuma moeda carregada.</div>

  return (
    <div className="space-y-5">
      {/* Cabeçalho */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">Dashboard</h2>
          <p className="text-xs text-muted-foreground">{data.total_verificacoes} trades verificados em tempo real</p>
        </div>
        {data.melhor_moeda && (
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Melhor oportunidade</p>
            <p className="text-sm font-bold text-green-400">
              {data.melhor_moeda.symbol} • {data.melhor_moeda.acuracias_reais?.['900']?.acuracia ?? '?'}% acc 15min
            </p>
          </div>
        )}
      </div>

      {/* Tabela de Acurácias por Horizonte */}
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <div className="bg-secondary/30 px-4 py-2 text-xs font-medium text-muted-foreground">
          ACURACIA REAL POR HORIZONTE
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/50 text-muted-foreground">
              <th className="text-left p-2 font-medium">Moeda</th>
              <th className="text-right p-2">5s</th>
              <th className="text-right p-2">15s</th>
              <th className="text-right p-2">30s</th>
              <th className="text-right p-2">60s</th>
              <th className="text-right p-2">5min</th>
              <th className="text-right p-2">15min</th>
              <th className="text-right p-2">30min</th>
              <th className="text-right p-2">1h</th>
              <th className="text-right p-2">Gerações</th>
            </tr>
          </thead>
          <tbody>
            {data.moedas.map((m: any) => (
              <tr key={m.symbol} className="border-b border-border/30 hover:bg-secondary/20">
                <td className="p-2 font-medium">
                  {m.symbol}
                  <span className="text-[10px] text-muted-foreground ml-1">${m.price.toLocaleString()}</span>
                </td>
                {['5','15','30','60','300','900','1800','3600'].map(h => {
                  const acc = m.acuracias_reais?.[h]
                  const val = acc?.acuracia ?? '-'
                  const color = typeof val === 'number' 
                    ? val >= 55 ? 'text-green-400' : val >= 48 ? 'text-yellow-400' : 'text-red-400'
                    : 'text-muted-foreground'
                  const total = acc?.total ?? 0
                  return (
                    <td key={h} className={`p-2 text-right font-mono ${color}`} title={`${acc?.acertos ?? 0}/${total} trades`}>
                      {typeof val === 'number' ? `${val}%` : val}
                    </td>
                  )
                })}
                <td className="p-2 text-right text-muted-foreground">{m.geracoes.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Grid inferior: Previsões + Horários */}
      <div className="grid grid-cols-2 gap-5">
        {/* Previsões Atuais */}
        <div className="rounded-lg border border-border/50 overflow-hidden">
          <div className="bg-secondary/30 px-4 py-2 text-xs font-medium text-muted-foreground">
            PREVISÕES ATUAIS
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border/50 text-muted-foreground">
                <th className="text-left p-2">Moeda</th>
                <th className="text-right p-2">5s</th>
                <th className="text-right p-2">5min</th>
                <th className="text-right p-2">15min</th>
                <th className="text-right p-2">1h</th>
                <th className="text-right p-2">RSI</th>
                <th className="text-right p-2">Regime</th>
              </tr>
            </thead>
            <tbody>
              {data.moedas.map((m: any) => (
                <tr key={m.symbol} className="border-b border-border/30">
                  <td className="p-2 font-medium">{m.symbol}</td>
                  <td className={`p-2 text-right font-mono ${m.previsoes['5s'] >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {m.previsoes['5s'] > 0 ? '+' : ''}{m.previsoes['5s']}%
                  </td>
                  <td className={`p-2 text-right font-mono ${m.previsoes['5min'] >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {m.previsoes['5min'] > 0 ? '+' : ''}{m.previsoes['5min']}%
                  </td>
                  <td className={`p-2 text-right font-mono font-bold ${m.previsoes['15min'] >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {m.previsoes['15min'] > 0 ? '+' : ''}{m.previsoes['15min']}%
                  </td>
                  <td className={`p-2 text-right font-mono ${m.previsoes['1h'] >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {m.previsoes['1h'] > 0 ? '+' : ''}{m.previsoes['1h']}%
                  </td>
                  <td className="p-2 text-right">{m.rsi}</td>
                  <td className="p-2 text-right text-muted-foreground">{m.regime}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Melhores Horários */}
        <div className="rounded-lg border border-border/50 overflow-hidden">
          <div className="bg-secondary/30 px-4 py-2 text-xs font-medium text-muted-foreground">
            MELHORES HORARIOS PARA OPERAR
          </div>
          <div className="p-3 space-y-2">
            {data.melhores_horarios.length === 0 && (
              <p className="text-xs text-muted-foreground">Dados insuficientes. Continue treinando.</p>
            )}
            {data.melhores_horarios.map((h: any, i: number) => (
              <div key={h.hora} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground w-8">{i + 1}o</span>
                <span className="font-mono font-bold">{h.hora}</span>
                <div className="flex-1 mx-3 h-1 bg-secondary rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-green-400 rounded-full"
                    style={{ width: `${Math.min(100, h.acuracia)}%` }}
                  />
                </div>
                <span className="font-mono text-green-400 w-12 text-right">{h.acuracia}%</span>
                <span className="text-muted-foreground w-12 text-right">{h.total} trades</span>
              </div>
            ))}
            {data.piores_horarios.length > 0 && (
              <div className="mt-3 pt-3 border-t border-border/30">
                <p className="text-[10px] text-muted-foreground mb-1">Evitar:</p>
                {data.piores_horarios.map((h: any) => (
                  <div key={h.hora} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-red-400">{h.hora}</span>
                    <span className="font-mono text-red-400">{h.acuracia}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Resumo */}
      <div className="text-center text-[10px] text-muted-foreground">
        Dados atualizados a cada 5 segundos. Acurácia real verificada comparando previsões com preços reais após o horizonte.
      </div>
    </div>
  )
}