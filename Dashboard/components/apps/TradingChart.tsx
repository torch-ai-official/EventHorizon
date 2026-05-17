"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { createChart, CrosshairMode, LineStyle, IChartApi, ISeriesApi, UTCTimestamp, CandlestickSeries, LineSeries } from "lightweight-charts"
import { ca } from "date-fns/locale"

interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
}

interface TradingChartProps {
  candles: Candle[]
  currentPrice: number       // preço em tempo real da Binance
  prediction: number
  timeframe?: number
  symbol?: string
  isActive?: boolean
}

function safeTime(t: any): UTCTimestamp {
  if (typeof t === "object") {
    return Math.floor(new Date(t.year, t.month - 1, t.day).getTime() / 1000) as UTCTimestamp
  }
  return Math.floor(Number(t)) as UTCTimestamp
}


// ─── EMA Calculator ──────────────────────────────────────────────────────────
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

// ─── Bollinger Bands ─────────────────────────────────────────────────────────
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

// ─── RSI ─────────────────────────────────────────────────────────────────────
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

export function TradingChart({ candles, currentPrice, prediction, timeframe = 5, symbol = "BTCUSDT", isActive = true }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const ema9Ref = useRef<ISeriesApi<"Line"> | null>(null)
  const ema21Ref = useRef<ISeriesApi<"Line"> | null>(null)
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null)
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null)
  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null)
  const predLineRef = useRef<ISeriesApi<"Line"> | null>(null)
  const lastTimeRef = useRef<number | null>(null)

  // ─── Smooth tick animation ────────────────────────────────────────────────
  const animFrameRef = useRef<number | null>(null)
  const animFromRef = useRef<number>(0)
  const animToRef = useRef<number>(0)
  const animStartRef = useRef<number>(0)
  const animDurationRef = useRef<number>(280)
  const currentCandleRef = useRef<Candle | null>(null)
  const isNewCandleRef = useRef<boolean>(false)

  // ─── Prediction smoothing (EMA sobre o score bruto) ──────────────────────
  const smoothPredRef = useRef<number>(0)   // valor suavizado atual
  const PRED_ALPHA = 0.15                   // 0.05=muito lento, 0.3=mais reativo

  const [hoverOHLC, setHoverOHLC] = useState<Candle | null>(null)
  const [rsi, setRsi] = useState<number>(50)
  const [lastPrice, setLastPrice] = useState<number | null>(null)
  const [priceChange, setPriceChange] = useState<number>(0)

  const resetedRef = useRef<number>(0)
  const versionRef = useRef(0)

  const candlesRef = useRef<Candle[]>([])

  // No topo do componente, antes dos efeitos:
  useEffect(() => {
    candlesRef.current = candles
  }, [candles])



  // ─── Build chart once ───────────────────────────────────────────────────────
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
        vertLine: {
          color: "#2a3a54",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#1a2a3a",
        },
        horzLine: {
          color: "#2a3a54",
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: "#1a2a3a",
        },
      },
      rightPriceScale: {
        borderColor: "#0d1a28",
        scaleMargins: { top: 0.08, bottom: 0.08 },
        textColor: "#4a6a8a",
      },
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
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    // ── Candles ──────────────────────────────────────────────────────────────
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00e676",
      downColor: "#ff3d57",
      borderUpColor: "#00e676",
      borderDownColor: "#ff3d57",
      wickUpColor: "#00a854",
      wickDownColor: "#cc2d44",
    })

    // ── EMA 9 ─────────────────────────────────────────────────────────────────
    const ema9 = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // ── EMA 21 ────────────────────────────────────────────────────────────────
    const ema21 = chart.addSeries(LineSeries, {
      color: "#38bdf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // ── Bollinger Upper ───────────────────────────────────────────────────────
    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(100,120,200,0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // ── Bollinger Lower ───────────────────────────────────────────────────────
    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(100,120,200,0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // ── Bollinger Mid ─────────────────────────────────────────────────────────
    const bbMid = chart.addSeries(LineSeries, {
      color: "rgba(100,120,200,0.2)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // ── Prediction line ───────────────────────────────────────────────────────
    const predLine = chart.addSeries(LineSeries, {
      color: "#d946ef",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    ema9Ref.current = ema9
    ema21Ref.current = ema21
    bbUpperRef.current = bbUpper
    bbLowerRef.current = bbLower
    bbMidRef.current = bbMid
    predLineRef.current = predLine

    // ── Crosshair hover ───────────────────────────────────────────────────────
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setHoverOHLC(null)
        return
      }
      const ohlc = param.seriesData.get(candleSeries) as any
      if (ohlc) {
        setHoverOHLC({ time: safeTime(param.time), ...ohlc })
      }
    })

    // ── Resize ────────────────────────────────────────────────────────────────
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current)
      chart.remove()
      chartRef.current = null
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    if (!isActive) {
      // Cancela qualquer animação em andamento
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
    }
  }, [isActive])

  // ─── Efeito 0: reseta ao trocar timeframe ─────────────────────────────────
  useEffect(() => {
    versionRef.current += 1

    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    // ⭐ NÃO LIMPA AS SÉRIES AQUI - apenas reseta as referências
    // candleSeriesRef.current?.setData([])  // ← REMOVA ESTA LINHA
    // ema9Ref.current?.setData([])          // ← REMOVA
    // ema21Ref.current?.setData([])         // ← REMOVA
    // bbUpperRef.current?.setData([])       // ← REMOVA
    // bbLowerRef.current?.setData([])       // ← REMOVA
    // bbMidRef.current?.setData([])         // ← REMOVA
    // predLineRef.current?.setData([])      // ← REMOVA

    // Reseta refs de estado
    lastTimeRef.current = null
    currentCandleRef.current = null
    animFromRef.current = 0
    animToRef.current = 0
    isNewCandleRef.current = false
    smoothPredRef.current = 0
    resetedRef.current += 1

  }, [timeframe])


    // ⭐ NOVO: Efeito 1.5 - Linha de previsão (roda sempre)
  useEffect(() => {
    if (!predLineRef.current || !currentPrice) return

    const now = Math.floor(Date.now() / 1000)
    const bucketTime = now - (now % timeframe)
    
    smoothPredRef.current = smoothPredRef.current + PRED_ALPHA * (prediction - smoothPredRef.current)
    const smoothedPred = smoothPredRef.current

    const futureTime = bucketTime + timeframe * 3
    const scaleFactor = currentPrice * 0.005
    // Escala logarítmica para movimentos percentuais
  const predicted = currentPrice * Math.exp(smoothedPred * 0.01)  // 1% por ponto
    
    predLineRef.current.setData([
      { time: safeTime(bucketTime), value: currentPrice },
      { time: safeTime(futureTime), value: predicted },
    ])
  }, [currentPrice, timeframe, prediction])

  // ─── Efeito ÚNICO: Gerencia TODOS os candles com animação ─────────────────
  useEffect(() => {
    if (!isActive) return
    if (!candleSeriesRef.current || !currentPrice) return

     console.log("🎯 Efeito Único rodando - candles:", candles.length, "currentPrice:", currentPrice)

    const myVersion = versionRef.current
    const now = Math.floor(Date.now() / 1000)
    const bucketTime = now - (now % timeframe)

    // ─── 1. Processa candles históricos (sem recriar tudo) ─────────────────
    if (candlesRef.current.length > 0 && lastTimeRef.current === null) {
      // Agrupa candles do backend no timeframe atual
      const agrupados = new Map<number, Candle>()
      
      for (const c of candlesRef.current) {
        const bucket = c.time - (c.time % timeframe)
        if (bucket >= bucketTime) continue
        
        if (!agrupados.has(bucket)) {
          agrupados.set(bucket, { 
            time: bucket, 
            open: c.open, 
            high: c.high, 
            low: c.low, 
            close: c.close 
          })
        } else {
          const existing = agrupados.get(bucket)!
          existing.high = Math.max(existing.high, c.high)
          existing.low = Math.min(existing.low, c.low)
          existing.close = c.close
        }
      }
      
      const closedCandles = Array.from(agrupados.values()).sort((a, b) => a.time - b.time)
      
      if (closedCandles.length > 0) {
        // Usa update em vez de setData para manter animação
        candleSeriesRef.current.setData(
          closedCandles.map(c => ({
            time: safeTime(c.time),
            open: c.open,
            high: Math.max(c.open, c.high, c.close),
            low: Math.min(c.open, c.low, c.close),
            close: c.close,
          }))
        )
        
        setRsi(calcRSI(closedCandles.length >= 15 ? closedCandles : candlesRef.current))
        
        if (closedCandles.length >= 2) {
          const prev = closedCandles[closedCandles.length - 2]
          const last = closedCandles[closedCandles.length - 1]
          setPriceChange(parseFloat((((last.close - prev.close) / prev.close) * 100).toFixed(3)))
        }
        
        if (ema9Ref.current) ema9Ref.current.setData(calcEMA(closedCandles, 9) as any)
        if (ema21Ref.current) ema21Ref.current.setData(calcEMA(closedCandles, 21) as any)
        
        if (closedCandles.length >= 20) {
          const bb = calcBollinger(closedCandles)
          bbUpperRef.current?.setData(bb.upper as any)
          bbLowerRef.current?.setData(bb.lower as any)
          bbMidRef.current?.setData(bb.mid as any)
        }
      }
    }

    // ─── 2. Atualiza/Anima o candle atual ──────────────────────────────────
    if (lastTimeRef.current === null) {
      // Primeiro preço do período
      lastTimeRef.current = bucketTime
      currentCandleRef.current = {
        time: bucketTime,
        open: currentPrice,
        high: currentPrice,
        low: currentPrice,
        close: currentPrice,
      }
      animFromRef.current = currentPrice
      animToRef.current = currentPrice
      isNewCandleRef.current = true
    }

    // ─── 3. Verifica se mudou de período ──────────────────────────────────
    if (bucketTime !== lastTimeRef.current) {
      // Fecha o candle anterior
      const prev = currentCandleRef.current
      if (prev && candleSeriesRef.current) {
        candleSeriesRef.current.update({
          time: safeTime(prev.time),
          open: prev.open,
          high: prev.high,
          low: prev.low,
          close: animToRef.current,
        })
      }
      
      // Inicia novo candle
      lastTimeRef.current = bucketTime
      currentCandleRef.current = {
        time: bucketTime,
        open: animToRef.current,
        high: Math.max(animToRef.current, currentPrice),
        low: Math.min(animToRef.current, currentPrice),
        close: currentPrice,
      }
      isNewCandleRef.current = true
    } else {
      // Atualiza o candle atual
      const c = currentCandleRef.current!
      currentCandleRef.current = {
        ...c,
        high: Math.max(c.high, currentPrice),
        low: Math.min(c.low, currentPrice),
        close: currentPrice,
      }
    }

    // ─── 4. Anima o candle atual ──────────────────────────────────────────
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    const prevAnimated = animToRef.current
    animFromRef.current = isNewCandleRef.current ? currentPrice : prevAnimated
    animToRef.current = currentPrice
    animStartRef.current = performance.now()
    animDurationRef.current = isNewCandleRef.current ? 400 : 280
    const birthAnim = isNewCandleRef.current
    isNewCandleRef.current = false

    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)
    const easeInOut = (t: number) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2

    const tick = (timestamp: number) => {
      if (versionRef.current !== myVersion) return
      if (!candleSeriesRef.current || !currentCandleRef.current) return

      const elapsed = timestamp - animStartRef.current
      const t = Math.min(elapsed / animDurationRef.current, 1)
      const c = currentCandleRef.current

      if (birthAnim) {
        const ease = easeInOut(t)
        const animatedClose = c.open + (currentPrice - c.open) * ease
        const wickScale = ease
        const highAnim = c.open + (c.high - c.open) * wickScale
        const lowAnim = c.open - (c.open - c.low) * wickScale

        candleSeriesRef.current!.update({
          time: safeTime(c.time),
          open: c.open,
          high: Math.max(c.open, highAnim, animatedClose),
          low: Math.min(c.open, lowAnim, animatedClose),
          close: parseFloat(animatedClose.toFixed(2)),
        })
        setLastPrice(parseFloat(animatedClose.toFixed(2)))
      } else {
        const animatedClose = animFromRef.current + (animToRef.current - animFromRef.current) * easeOut(t)
        candleSeriesRef.current!.update({
          time: safeTime(c.time),
          open: c.open,
          high: Math.max(c.high, animatedClose),
          low: Math.min(c.low, animatedClose),
          close: parseFloat(animatedClose.toFixed(2)),
        })
        setLastPrice(parseFloat(animatedClose.toFixed(2)))
      }

      if (t < 1) {
        animFrameRef.current = requestAnimationFrame(tick)
      } else {
        animFrameRef.current = null
      }
    }

    animFrameRef.current = requestAnimationFrame(tick)
    chartRef.current?.timeScale().scrollToRealTime()
    
  }, [currentPrice, timeframe, isActive])  // ⭐ Dependências corretas


  // ─── Derived display values ──────────────────────────────────────────────
  const displayCandle = hoverOHLC ?? (candles.length ? candles[candles.length - 1] : null)
  const isGreen = displayCandle ? displayCandle.close >= displayCandle.open : true
  const rsiColor = rsi > 70 ? "#ff3d57" : rsi < 30 ? "#00e676" : "#f59e0b"

  return (
    <div className="relative w-full rounded-xl overflow-hidden select-none" style={{ background: "#060b14", fontFamily: "'JetBrains Mono', monospace" }}>

      {/* ── Top Bar ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b" style={{ borderColor: "#0d1a28" }}>

        {/* Symbol + Price */}
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
              <span key={label as string}>
                <span style={{ color: "#2a4a6a" }}>{label} </span>
                <span style={{ color: label === "H" ? "#00e676" : label === "L" ? "#ff3d57" : "#8b9ab0" }}>
                  {(val as number).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </span>
            ))}
          </div>
        )}

        {/* RSI Badge */}
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

      {/* ── Indicator Legend ─────────────────────────────────────────────────── */}
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

        {/* Prediction direction */}
        <div className="ml-auto flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: prediction > 0 ? "#00e676" : prediction < 0 ? "#ff3d57" : "#f59e0b" }} />
          <span className="text-[10px] font-semibold"
            style={{ color: prediction > 0 ? "#00e676" : prediction < 0 ? "#ff3d57" : "#f59e0b" }}>
            {prediction > 1 ? "STRONG BUY" : prediction > 0 ? "BUY" : prediction < -1 ? "STRONG SELL" : prediction < 0 ? "SELL" : "NEUTRAL"}
          </span>
        </div>
      </div>

      {/* ── Chart ─────────────────────────────────────────────────────────────── */}
      <div ref={containerRef} className="w-full" style={{ height: 340 }} />

      {/* ── RSI Meter Bar ────────────────────────────────────────────────────── */}
      <div className="px-4 py-2 flex items-center gap-3" style={{ background: "#060b14", borderTop: "1px solid #0d1a28" }}>
        <span className="text-[10px] w-6" style={{ color: "#2a4a6a" }}>RSI</span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "#0d1a28" }}>
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${rsi}%`,
              background: `linear-gradient(90deg, #00e676 0%, #f59e0b 50%, #ff3d57 100%)`,
              clipPath: `inset(0 ${100 - rsi}% 0 0 round 4px)`
            }}
          />
        </div>
        {/* Zone labels */}
        <div className="flex gap-4 text-[9px]" style={{ color: "#1a3a5a" }}>
          <span style={{ color: "#00a854" }}>OS 30</span>
          <span>50</span>
          <span style={{ color: "#cc2d44" }}>OB 70</span>
        </div>
      </div>

      {/* ── Watermark ───────────────────────────────────────────────────────── */}
      <div className="absolute top-16 left-1/2 -translate-x-1/2 pointer-events-none select-none text-center" style={{ opacity: 0.03 }}>
        <div className="text-5xl font-black tracking-widest" style={{ color: "#fff" }}>{symbol.replace("USDT", "")}</div>
      </div>
    </div>
  )
}