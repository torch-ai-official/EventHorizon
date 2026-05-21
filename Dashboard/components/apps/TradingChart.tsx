import { useEffect, useRef, useState } from "react"
import { createChart, CrosshairMode, LineStyle, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, LineSeries, AreaSeries } from "lightweight-charts"

interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
}

interface TradingChartProps {
  candles: Candle[]
  currentPrice: number
  prediction: number
  timeframe?: number
  symbol?: string
  isActive?: boolean
  chartType?: "candlestick" | "line" | "area"  // ⭐ NOVO
  showIndicators?: boolean                      // ⭐ NOVO
}
function safeTime(t: any): UTCTimestamp {
  return Math.floor(Number(t)) as UTCTimestamp
}

function calcEMA(data: Candle[], period: number) {
  const k = 2 / (period + 1)
  const result: { time: number; value: number }[] = []
  let ema = data[0]?.close ?? 0
  for (const c of data) {
    ema = c.close * k + ema * (1 - k)
    result.push({ time: safeTime(c.time), value: parseFloat(ema.toFixed(4)) })
  }
  return result
}

function calcBollinger(data: Candle[], period = 20, mult = 2) {
  const upper: { time: number; value: number }[] = []
  const lower: { time: number; value: number }[] = []
  const mid: { time: number; value: number }[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) continue
    const slice = data.slice(i - period + 1, i + 1).map(c => c.close)
    const mean = slice.reduce((a, b) => a + b, 0) / period
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period
    const sd = Math.sqrt(variance)
    upper.push({ time: safeTime(data[i].time), value: parseFloat((mean + mult * sd).toFixed(4)) })
    lower.push({ time: safeTime(data[i].time), value: parseFloat((mean - mult * sd).toFixed(4)) })
    mid.push({ time: safeTime(data[i].time), value: parseFloat(mean.toFixed(4)) })
  }
  return { upper, lower, mid }
}

function calcRSI(data: Candle[], period = 14): number {
  if (data.length < period + 1) return 50
  const closes = data.slice(-(period + 1)).map(c => c.close)
  let gains = 0, losses = 0
  for (let i = 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1]
    if (diff >= 0) gains += diff
    else losses -= diff
  }
  const rs = gains / (losses || 1)
  return parseFloat((100 - 100 / (1 + rs)).toFixed(2))
}

export function TradingChart({ candles, currentPrice, prediction, timeframe = 5, symbol = "BTCUSDT", isActive = true, chartType = "candlestick", showIndicators = true }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const ema9Ref = useRef<ISeriesApi<"Line"> | null>(null)
  const ema21Ref = useRef<ISeriesApi<"Line"> | null>(null)
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null)
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null)
  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null)
  const predLineRef = useRef<ISeriesApi<"Line"> | null>(null)
  
  // ⭐ Usamos setTimeout em vez de requestAnimationFrame para não congelar
  const animationIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const targetPriceRef = useRef<number>(currentPrice)
  const currentAnimatedPriceRef = useRef<number>(currentPrice)
  
  const [hoverOHLC, setHoverOHLC] = useState<Candle | null>(null)
  const [rsi, setRsi] = useState(50)
  const [lastPrice, setLastPrice] = useState<number | null>(null)
  const [priceChange, setPriceChange] = useState(0)
  const [currentCandleTime, setCurrentCandleTime] = useState<number | null>(null)
  const containerOuterRef = useRef<HTMLDivElement>(null)
  const chartContainerRef = useRef<HTMLDivElement>(null)

  const [isFullscreen, setIsFullscreen] = useState(false)

  const toggleFullscreen = async () => {
    if (!containerOuterRef.current) return
    
    if (!isFullscreen) {
      await containerOuterRef.current.requestFullscreen()
      setIsFullscreen(true)
    } else {
      await document.exitFullscreen()
      setIsFullscreen(false)
    }
  }

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
      // Força redimensionamento do gráfico
      setTimeout(() => {
        chartRef.current?.applyOptions({ 
          width: containerOuterRef.current?.clientWidth || 0,
          height: isFullscreen ? window.innerHeight - 180 : 600
        })
      }, 100)
    }
    
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [isFullscreen])

  // ⭐ Atualiza o preço alvo
  useEffect(() => {
    targetPriceRef.current = currentPrice
  }, [currentPrice])

  // ⭐ Animação suave usando setInterval (não congela em segundo plano)
  useEffect(() => {
    if (!isActive) {
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current)
        animationIntervalRef.current = null
      }
      return
    }

    if (animationIntervalRef.current) {
      clearInterval(animationIntervalRef.current)
    }

    animationIntervalRef.current = setInterval(() => {
      if (!candleSeriesRef.current) return
      
      // Move suavemente em direção ao preço alvo
      const diff = targetPriceRef.current - currentAnimatedPriceRef.current
      if (Math.abs(diff) < 0.01) {
        currentAnimatedPriceRef.current = targetPriceRef.current
      } else {
        currentAnimatedPriceRef.current += diff * 0.3 // 30% do caminho por frame
      }
      
      const animatedPrice = currentAnimatedPriceRef.current
      const now = Math.floor(Date.now() / 1000)
      const bucketTime = now - (now % timeframe)
      
      // Encontra ou cria o candle atual
      const existingCandle = candles.find(c => c.time === bucketTime)
      
      if (existingCandle) {
        candleSeriesRef.current!.update({
          time: safeTime(bucketTime),
          open: existingCandle.open,
          high: Math.max(existingCandle.high, animatedPrice),
          low: Math.min(existingCandle.low, animatedPrice),
          close: animatedPrice,
        })
      } else {
        candleSeriesRef.current!.update({
          time: safeTime(bucketTime),
          open: animatedPrice,
          high: animatedPrice,
          low: animatedPrice,
          close: animatedPrice,
        })
      }
      
      setLastPrice(animatedPrice)
      chartRef.current?.timeScale().scrollToRealTime()
    }, 50) // 20 FPS, suave mas não pesado

    return () => {
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current)
        animationIntervalRef.current = null
      }
    }
  }, [isActive, timeframe, candles])

  // ⭐ Recria a série quando o tipo de gráfico muda
  useEffect(() => {
    if (!chartRef.current) return

    // Remove a série antiga
    if (candleSeriesRef.current) {
      chartRef.current.removeSeries(candleSeriesRef.current)
      candleSeriesRef.current = null
    }

    // Cria a nova série baseada no tipo
    let newSeries: any = null
    
    if (chartType === "candlestick") {
      newSeries = chartRef.current.addSeries(CandlestickSeries, {
        upColor: "#00e676",
        downColor: "#ff3d57",
        borderUpColor: "#00e676",
        borderDownColor: "#ff3d57",
        wickUpColor: "#00a854",
        wickDownColor: "#cc2d44",
      })
    } else if (chartType === "line") {
      newSeries = chartRef.current.addSeries(LineSeries, {
        color: "#38bdf8",
        lineWidth: 2,
        priceLineVisible: true,
        lastValueVisible: true,
      })
    } else {
      newSeries = chartRef.current.addSeries(AreaSeries, {
      topColor: "rgba(0, 230, 118, 0.4)",   // Verde transparente no topo
      bottomColor: "rgba(0, 230, 118, 0.0)", // Transparente na base
      lineColor: "#00e676",                  // Linha verde vibrante
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      crosshairMarkerBorderColor: "#00e676",
      crosshairMarkerBackgroundColor: "#1a2a3a",
    })
    }

    candleSeriesRef.current = newSeries

    // Recarrega os dados históricos
    const now = Math.floor(Date.now() / 1000)
    const bucketTime = now - (now % timeframe)
    
    const closedCandles = candles
      .filter(c => c.time < bucketTime)
      .sort((a, b) => a.time - b.time)

    if (closedCandles.length > 0) {
      if (chartType === "candlestick") {
        newSeries.setData(
          closedCandles.map(c => ({
            time: safeTime(c.time),
            open: c.open,
            high: Math.max(c.open, c.high, c.close),
            low: Math.min(c.open, c.low, c.close),
            close: c.close,
          }))
        )
      } else {
        newSeries.setData(
          closedCandles.map(c => ({
            time: safeTime(c.time),
            value: c.close,
          }))
        )
      }
    }

  }, [chartType, timeframe, candles])

  // ⭐ Reset do preço animado quando o timeframe muda
  useEffect(() => {
    currentAnimatedPriceRef.current = currentPrice
  }, [timeframe, currentPrice])

  // ⭐ Build chart once (MODIFICADO)
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#060b14" },
        textColor: "#8b9ab0",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#0d1520", style: LineStyle.Solid },
        horzLines: { color: "#0d1520", style: LineStyle.Solid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#2a3a54", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#1a2a3a" },
        horzLine: { color: "#2a3a54", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#1a2a3a" },
      },
      rightPriceScale: { borderColor: "#0d1a28", scaleMargins: { top: 0.08, bottom: 0.08 }, textColor: "#4a6a8a" },
      timeScale: {
        borderColor: "#0d1a28",
        timeVisible: true,
        secondsVisible: timeframe < 60,
        tickMarkFormatter: (time: number) => {
          const d = new Date(time * 1000)
          const h = d.getHours().toString().padStart(2, "0")
          const m = d.getMinutes().toString().padStart(2, "0")
          const s = d.getSeconds().toString().padStart(2, "0")
          return timeframe < 60 ? `${h}:${m}:${s}` : `${h}:${m}`
        },
      },
      width: containerRef.current.clientWidth,
      height: 600,
    })

    // ⭐ Série principal baseada no tipo de gráfico
    let mainSeries: any = null
    
    if (chartType === "candlestick") {
      mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#00e676", downColor: "#ff3d57",
        borderUpColor: "#00e676", borderDownColor: "#ff3d57",
        wickUpColor: "#00a854", wickDownColor: "#cc2d44",
      })
    } else if (chartType === "line") {
      mainSeries = chart.addSeries(LineSeries, {
        color: "#38bdf8",
        lineWidth: 2,
        priceLineVisible: true,
        lastValueVisible: true,
      })
    } else if (chartType === "area") {
      mainSeries = chart.addSeries(AreaSeries, {
        topColor: "rgba(0, 230, 118, 0.4)",
        bottomColor: "rgba(0, 230, 118, 0.0)",
        lineColor: "#00e676",
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: "#00e676",
        crosshairMarkerBackgroundColor: "#1a2a3a",
      })
    }

    candleSeriesRef.current = mainSeries

    // ⭐ Só adiciona indicadores se showIndicators for true
    if (showIndicators) {
      ema9Ref.current = chart.addSeries(LineSeries, { 
        color: "#f59e0b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false 
      })
      ema21Ref.current = chart.addSeries(LineSeries, { 
        color: "#38bdf8", lineWidth: 1, priceLineVisible: false, lastValueVisible: false 
      })
      bbUpperRef.current = chart.addSeries(LineSeries, { 
        color: "rgba(100,120,200,0.4)", lineWidth: 1, lineStyle: LineStyle.Dashed 
      })
      bbLowerRef.current = chart.addSeries(LineSeries, { 
        color: "rgba(100,120,200,0.4)", lineWidth: 1, lineStyle: LineStyle.Dashed 
      })
      bbMidRef.current = chart.addSeries(LineSeries, { 
        color: "rgba(100,120,200,0.2)", lineWidth: 1, lineStyle: LineStyle.Dotted 
      })
    }

    // Linha de previsão (sempre adiciona)
    predLineRef.current = chart.addSeries(LineSeries, { 
      color: "#d946ef", lineWidth: 2, lineStyle: LineStyle.Dashed 
    })

    chartRef.current = chart

    // Crosshair hover (adaptado para line/area)
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHoverOHLC(null)
        return
      }
      const data = param.seriesData.get(mainSeries) as any
      if (data && chartType === "candlestick") {
        setHoverOHLC({ time: safeTime(param.time), open: data.open, high: data.high, low: data.low, close: data.close })
      } else if (data) {
        setLastPrice(data.value)
      }
    })

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      if (animationIntervalRef.current) clearInterval(animationIntervalRef.current)
      chart.remove()
      chartRef.current = null
    }
  }, [timeframe, chartType, showIndicators])  // ⭐ Dependências atualizadas

  // ⭐ Carrega os candles históricos e REAGRUPAR pelo timeframe atual
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return

    const now = Math.floor(Date.now() / 1000)
    const bucketTime = now - (now % timeframe)
    
    // ⭐ REAGRUPAR candles pelo timeframe atual (NÃO usar os candles como estão)
    const groupedCandles = new Map<number, Candle>()
    
    for (const c of candles) {
      // Agrupa pelo bucket do timeframe ATUAL
      const bucket = c.time - (c.time % timeframe)
      if (bucket >= bucketTime) continue  // Ignora candle atual
      
      if (!groupedCandles.has(bucket)) {
        groupedCandles.set(bucket, {
          time: bucket,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })
      } else {
        const existing = groupedCandles.get(bucket)!
        existing.high = Math.max(existing.high, c.high)
        existing.low = Math.min(existing.low, c.low)
        existing.close = c.close
      }
    }
    
    const closedCandles = Array.from(groupedCandles.values()).sort((a, b) => a.time - b.time)

    if (closedCandles.length > 0) {
      if (chartType === "candlestick") {
        candleSeriesRef.current.setData(
          closedCandles.map(c => ({
            time: safeTime(c.time),
            open: c.open,
            high: Math.max(c.open, c.high, c.close),
            low: Math.min(c.open, c.low, c.close),
            close: c.close,
          }))
        )
      } else {
        candleSeriesRef.current.setData(
          closedCandles.map(c => ({
            time: safeTime(c.time),
            value: c.close,
          }))
        )
      }
      
      setRsi(calcRSI(closedCandles))
      
      if (closedCandles.length >= 2) {
        const prev = closedCandles[closedCandles.length - 2]
        const last = closedCandles[closedCandles.length - 1]
        setPriceChange(parseFloat((((last.close - prev.close) / prev.close) * 100).toFixed(3)))
      }

      // Só atualiza indicadores se estiverem ativos
      if (showIndicators && ema9Ref.current && closedCandles.length >= 9) {
        ema9Ref.current.setData(calcEMA(closedCandles, 9) as any)
      }
      if (showIndicators && ema21Ref.current && closedCandles.length >= 21) {
        ema21Ref.current.setData(calcEMA(closedCandles, 21) as any)
      }
      if (showIndicators && closedCandles.length >= 20) {
        const bb = calcBollinger(closedCandles)
        bbUpperRef.current?.setData(bb.upper as any)
        bbLowerRef.current?.setData(bb.lower as any)
        bbMidRef.current?.setData(bb.mid as any)
      }
    }
    
    // Define o candle atual baseado no timeframe atual
    const currentCandle = candles.find(c => {
      const bucket = c.time - (c.time % timeframe)
      return bucket === bucketTime
    })
    
    if (currentCandle) {
      setCurrentCandleTime(bucketTime)
      currentAnimatedPriceRef.current = currentCandle.close
    }
  }, [candles, timeframe, chartType, showIndicators])

  // ⭐ Linha de previsão (atualiza diretamente, sem animação)
  useEffect(() => {
    if (!predLineRef.current || !currentPrice) return

    const now = Math.floor(Date.now() / 1000)
    const bucketTime = now - (now % timeframe)
    const futureTime = bucketTime + timeframe * 3
    const predicted = currentPrice * Math.exp(prediction * 0.01)
    
    predLineRef.current.setData([
      { time: safeTime(bucketTime), value: currentPrice },
      { time: safeTime(futureTime), value: predicted },
    ])
  }, [currentPrice, timeframe, prediction])

  // ⭐ Atualiza o preço exibido no topo
  useEffect(() => {
    if (currentPrice) {
      // O lastPrice é atualizado pela animação
    }
  }, [currentPrice])

  const displayCandle = hoverOHLC ?? (candles.length ? candles[candles.length - 1] : null)
  const isGreen = displayCandle ? displayCandle.close >= displayCandle.open : true
  const rsiColor = rsi > 70 ? "#ff3d57" : rsi < 30 ? "#00e676" : "#f59e0b"

  return (
    <div className="relative w-full rounded-xl overflow-hidden select-none" style={{ background: "#060b14", fontFamily: "'JetBrains Mono', monospace" }}>
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b" style={{ borderColor: "#0d1a28" }}>
        <div className="flex items-center gap-4">
          <div>
            <span className="text-xs font-bold tracking-widest" style={{ color: "#8b9ab0" }}>{symbol}</span>
            {lastPrice !== null && (
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-lg font-bold tabular-nums" style={{ color: isGreen ? "#00e676" : "#ff3d57" }}>
                  {lastPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-xs font-semibold px-1.5 py-0.5 rounded`}
                  style={{
                    background: priceChange >= 0 ? "rgba(0,230,118,0.12)" : "rgba(255,61,87,0.12)",
                    color: priceChange >= 0 ? "#00e676" : "#ff3d57"
                  }}>
                  {priceChange >= 0 ? "+" : ""}{priceChange}%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* OHLC Hover Info */}
        {displayCandle && (
          <div className="flex gap-4 text-xs tabular-nums" style={{ color: "#4a6a8a" }}>
            {[
              ["O", displayCandle.open],
              ["H", displayCandle.high],
              ["L", displayCandle.low],
              ["C", displayCandle.close],
            ].map(([label, val]) => (
              <span key={label}>
                <span style={{ color: "#2a4a6a" }}>{label} </span>
                <span style={{ color: label === "H" ? "#00e676" : label === "L" ? "#ff3d57" : "#8b9ab0" }}>
                  {(val as number).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2">
          <div className="text-xs px-2 py-1 rounded" style={{ background: "rgba(0,0,0,0.4)", border: "1px solid #0d1a28" }}>
            <span style={{ color: "#2a4a6a" }}>RSI </span>
            <span className="font-bold" style={{ color: rsiColor }}>{rsi}</span>
          </div>
          <div className="text-xs px-2 py-1 rounded" style={{ background: "rgba(0,0,0,0.4)", border: "1px solid #0d1a28" }}>
            <span style={{ color: "#2a4a6a" }}>TF </span>
            <span style={{ color: "#4a8a6a" }}>{timeframe}s</span>
          </div>
        </div>
      </div>

      {/* Indicator Legend */}
      <div className="flex gap-4 px-4 py-1.5" style={{ background: "rgba(0,0,0,0.3)" }}>
        {[
          { label: "EMA 9", color: "#f59e0b" },
          { label: "EMA 21", color: "#38bdf8" },
          { label: "BB(20,2)", color: "rgba(100,120,200,0.6)" },
          { label: "Signal", color: "#d946ef" },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-5 h-px" style={{ background: color, borderTop: `1px solid ${color}` }} />
            <span className="text-[10px]" style={{ color: "#3a5a7a" }}>{label}</span>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: prediction > 0 ? "#00e676" : prediction < 0 ? "#ff3d57" : "#f59e0b" }} />
          <span className="text-[10px] font-semibold"
            style={{ color: prediction > 0 ? "#00e676" : prediction < 0 ? "#ff3d57" : "#f59e0b" }}>
            {prediction > 1 ? "STRONG BUY" : prediction > 0 ? "BUY" : prediction < -1 ? "STRONG SELL" : prediction < 0 ? "SELL" : "NEUTRAL"}
          </span>
        </div>
      </div>

      {/* Chart */}
      <div ref={containerRef} className="w-full" style={{ height: 600 }} />

      {/* RSI Meter Bar */}
      <div className="px-4 py-2 flex items-center gap-3" style={{ background: "#060b14", borderTop: "1px solid #0d1a28" }}>
        <span className="text-[10px] w-6" style={{ color: "#2a4a6a" }}>RSI</span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "#0d1a28" }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${rsi}%`,
              background: `linear-gradient(90deg, #00e676 0%, #f59e0b 50%, #ff3d57 100%)`,
            }}
          />
        </div>
        <div className="flex gap-4 text-[9px]" style={{ color: "#1a3a5a" }}>
          <span style={{ color: "#00a854" }}>OS 30</span>
          <span>50</span>
          <span style={{ color: "#cc2d44" }}>OB 70</span>
        </div>
      </div>

      {/* Watermark */}
      <div className="absolute top-16 left-1/2 -translate-x-1/2 pointer-events-none select-none text-center" style={{ opacity: 0.03 }}>
        <div className="text-5xl font-black tracking-widest" style={{ color: "#fff" }}>{symbol.replace("USDT", "")}</div>
      </div>
    </div>
  )
}