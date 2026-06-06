"use client"

import { useState, useRef, useEffect, useCallback } from "react"

interface Message {
  role: "user" | "assistant"
  content: string
  id: string
  liked?: boolean
  disliked?: boolean
}

// ⭐ COMPONENTE DO LOGO MENTETORCH (reutilizável)
function LogoMenteTorch({ size = 28, opacity = 0.9, animated = false }: { size?: number; opacity?: number; animated?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10.5" stroke="currentColor" strokeWidth="1.5" />
      <path 
        d="M6.5 17V10l3 5 2.5-5 2.5 5 3-5v7" 
        stroke="currentColor" 
        strokeWidth="2.2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
        fill="none"
      />
      <circle cx="12" cy="6.5" r="2" fill="currentColor" opacity={opacity}>
        {animated && (
          <animate attributeName="opacity" values="0.9;0.3;0.9" dur="2.5s" repeatCount="indefinite" />
        )}
      </circle>
    </svg>
  )
}

export function ChatBot() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [hasMoved, setHasMoved] = useState(false)
  const chatRef = useRef<HTMLDivElement>(null)
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }
  
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('[data-drag-handle]')) {
      setIsDragging(true)
      setHasMoved(false)
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y
      })
    }
  }, [position])
  
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging) {
      const newX = e.clientX - dragStart.x
      const newY = e.clientY - dragStart.y
      setPosition({ x: newX, y: newY })
      if (Math.abs(newX) > 3 || Math.abs(newY) > 3) {
        setHasMoved(true)
      }
    }
  }, [isDragging, dragStart])
  
  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])
  
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])
  
  const sendMessage = async () => {
    if (!input.trim() || loading) return
    
    const userMsg: Message = {
      role: "user",
      content: input,
      id: Date.now().toString()
    }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setLoading(true)
    
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://lucas4567-trading-ai.hf.space"}/chatbot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          pergunta: input, 
          moeda: "BTCUSDT"
        })
      })
      const data = await response.json()
      
      const assistantMsg: Message = {
        role: "assistant",
        content: data.resposta || "Desculpe, não consegui processar.",
        id: (Date.now() + 1).toString()
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "❌ Erro ao conectar com o assistente.",
        id: (Date.now() + 1).toString()
      }])
    } finally {
      setLoading(false)
    }
  }
  
  const copyMessage = async (content: string, id: string) => {
    await navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }
  
  const likeMessage = (id: string) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, liked: true, disliked: false } : msg
    ))
  }
  
  const dislikeMessage = (id: string) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, disliked: true, liked: false } : msg
    ))
  }
  
  const regenerateMessage = async (index: number) => {
    if (index === 0) return
    const userMsg = messages[index - 1]
    if (userMsg.role !== "user") return
    
    setMessages(prev => prev.filter((_, i) => i !== index))
    setInput(userMsg.content)
    setTimeout(() => sendMessage(), 100)
  }
  
  return (
    <>
      {/* ⭐ BOTÃO FLUTUANTE COM LOGO */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl bg-neutral-800 border border-neutral-700 text-neutral-300 shadow-2xl flex items-center justify-center hover:bg-neutral-700 hover:border-neutral-600 hover:text-white transition-all active:scale-95 group"
        title="MenteTorch Assistant"
      >
        {isOpen ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        ) : (
          <LogoMenteTorch size={28} animated={true} />
        )}
      </button>
      
      {/* ⭐ JANELA DO CHAT */}
      {isOpen && (
        <div
          ref={chatRef}
          onMouseDown={handleMouseDown}
          style={{
            position: 'fixed',
            left: position.x || undefined,
            top: position.y || undefined,
            bottom: position.x === 0 && position.y === 0 ? '5rem' : undefined,
            right: position.x === 0 && position.y === 0 ? '1.5rem' : undefined,
            zIndex: 50,
            width: '440px',
            height: '650px',
            cursor: isDragging ? 'grabbing' : 'default',
            userSelect: isDragging ? 'none' : 'auto',
          }}
          className="bg-[#0f0f0f] border border-neutral-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        >
          {/* ⭐ HEADER COM LOGO */}
          <div 
            data-drag-handle
            className="px-5 py-4 border-b border-neutral-800 flex items-center gap-3 bg-[#0f0f0f] cursor-grab active:cursor-grabbing"
          >
            <div className="w-9 h-9 rounded-xl bg-neutral-800 flex items-center justify-center text-neutral-300">
              <LogoMenteTorch size={18} opacity={0.8} />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-neutral-200">MenteTorch Assistant</h3>
              <p className="text-[11px] text-neutral-500">Powered by Groq · Llama 3.1</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg hover:bg-neutral-800 text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          
          {/* ⭐ MESSAGES */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6 bg-[#0a0a0a]">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                {/* ⭐ LOGO GRANDE NO CENTRO */}
                <div className="w-20 h-20 rounded-3xl bg-neutral-800 flex items-center justify-center mb-6 text-neutral-300">
                  <LogoMenteTorch size={36} opacity={0.7} animated={true} />
                </div>
                <h3 className="text-neutral-200 text-lg font-medium mb-2">MenteTorch Assistant</h3>
                <p className="text-neutral-500 text-sm leading-relaxed mb-8">
                  Análise de mercado inteligente baseada em dados reais.
                </p>
                <div className="grid grid-cols-1 gap-2.5 w-full">
                  {[
                    "Análise do mercado agora",
                    "Como funciona o sistema de IA?",
                    "Qual horizonte é mais confiável?",
                    "Sugestão de gestão de risco"
                  ].map(q => (
                    <button
                      key={q}
                      onClick={() => { setInput(q); setTimeout(() => sendMessage(), 100); }}
                      className="text-left text-sm px-4 py-3 rounded-xl border border-neutral-800 text-neutral-400 hover:text-neutral-200 hover:border-neutral-700 hover:bg-neutral-800/50 transition-all bg-neutral-900/30"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            
            {messages.map((msg, i) => (
              <div key={msg.id} className="group">
                <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-neutral-800 text-neutral-200 rounded-br-md' 
                      : 'bg-neutral-900 text-neutral-300 rounded-bl-md border border-neutral-800'
                  }`}>
                    {msg.content}
                  </div>
                </div>
                
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-1 mt-1.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => copyMessage(msg.content, msg.id)}
                      className="p-1.5 rounded-lg hover:bg-neutral-800 text-neutral-600 hover:text-neutral-300 transition-colors"
                      title="Copiar"
                    >
                      {copiedId === msg.id ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                      )}
                    </button>
                    
                    <button
                      onClick={() => regenerateMessage(i)}
                      className="p-1.5 rounded-lg hover:bg-neutral-800 text-neutral-600 hover:text-neutral-300 transition-colors"
                      title="Refazer resposta"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                    </button>
                    
                    <button
                      onClick={() => likeMessage(msg.id)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        msg.liked 
                          ? 'bg-emerald-500/10 text-emerald-400' 
                          : 'hover:bg-neutral-800 text-neutral-600 hover:text-neutral-300'
                      }`}
                      title="Gostei"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill={msg.liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    </button>
                    
                    <button
                      onClick={() => dislikeMessage(msg.id)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        msg.disliked 
                          ? 'bg-red-500/10 text-red-400' 
                          : 'hover:bg-neutral-800 text-neutral-600 hover:text-neutral-300'
                      }`}
                      title="Não gostei"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill={msg.disliked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                    </button>
                  </div>
                )}
              </div>
            ))}
            
            {/* ⭐ LOADING COM LOGO PULSANTE */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-3">
                  <div className="text-neutral-500">
                    <LogoMenteTorch size={20} opacity={0.5} animated={true} />
                  </div>
                  <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-neutral-600 animate-bounce" />
                    <div className="w-2.5 h-2.5 rounded-full bg-neutral-600 animate-bounce" style={{animationDelay: '0.15s'}} />
                    <div className="w-2.5 h-2.5 rounded-full bg-neutral-600 animate-bounce" style={{animationDelay: '0.3s'}} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          {/* ⭐ INPUT */}
          <div className="p-4 border-t border-neutral-800 bg-[#0f0f0f]">
            <div className="flex gap-2 items-center bg-neutral-900 rounded-xl px-4 py-2.5 border border-neutral-800 focus-within:border-neutral-600 transition-all">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Pergunte sobre o mercado..."
                className="flex-1 bg-transparent text-sm text-neutral-200 placeholder-neutral-500 outline-none"
                disabled={loading}
              />
              <button 
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="p-2 rounded-lg hover:bg-neutral-800 disabled:opacity-30 transition-all text-neutral-400 hover:text-white"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
            <p className="text-[10px] text-neutral-600 text-center mt-2">
              MenteTorch Assistant · Respostas podem conter imprecisões
            </p>
          </div>
        </div>
      )}
    </>
  )
}