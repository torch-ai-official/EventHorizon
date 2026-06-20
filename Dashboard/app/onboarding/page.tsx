"use client"

// ============================================================
// ONBOARDING COMPLETO — 5 ETAPAS + TELA DE PLANO RECOMENDADO
// app/onboarding/page.tsx
// ============================================================

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import {
  TrendingUp, ChevronRight, ChevronLeft, Check,
  Zap, Clock, Shield, Coins, Bell,
  Star, Loader2, CheckCircle2
} from "lucide-react"
import { criarClienteNavegador } from "@/lib/supabase-client"

import { salvarOnboarding } from "@/lib/supabase-client"
import { calcularPlanoRecomendado, ROTULOS } from "@/lib/onboarding"

// ============================================================
// TIPOS LOCAIS (para evitar erros de importação)
// ============================================================

type NivelExperiencia = "iniciante" | "intermediario" | "avancado" | "profissional"
type HorasDia = "1-2h" | "3-5h" | "6-8h" | "integral"
type ApetiteRisco = "conservador" | "moderado" | "agressivo" | "insano"
type QtdMoedas = "3" | "10" | "20+"
type TipoAlerta = "navegador" | "telegram" | "nenhum"

interface RespostasOnboarding {
  nivel_experiencia: NivelExperiencia
  horas_dia: HorasDia
  apetite_risco: ApetiteRisco
  qtd_moedas: QtdMoedas
  alertas_tipo: TipoAlerta
}

// ============================================================
// PLANOS
// ============================================================

const PLANOS = {
  basico: {
    id: "basico" as const,
    nome: "Básico",
    preco: 97,
    moedas: 3,
    alertas: false,
    telegram: false,
    api_access: false,
  },
  pro: {
    id: "pro" as const,
    nome: "Pro",
    preco: 197,
    moedas: 10,
    alertas: true,
    telegram: true,
    api_access: false,
  },
  enterprise: {
    id: "enterprise" as const,
    nome: "Enterprise",
    preco: 497,
    moedas: 20,
    alertas: true,
    telegram: true,
    api_access: true,
  },
}

// ============================================================
// CONFIGURAÇÃO DAS ETAPAS
// ============================================================

interface OpcaoConfig {
  valor: string
  rotulo: string
  descricao: string
  emoji: string
}

interface EtapaConfig {
  id: number
  titulo: string
  subtitulo: string
  icone: any
  campo: keyof RespostasOnboarding
  opcoes: OpcaoConfig[]
}

const ETAPAS: EtapaConfig[] = [
  {
    id: 1,
    titulo: "Nível de Experiência",
    subtitulo: "Como você se descreveria como trader?",
    icone: Star,
    campo: "nivel_experiencia",
    opcoes: [
      { valor: "iniciante", rotulo: "Iniciante", descricao: "Ainda estou aprendendo sobre trading", emoji: "🌱" },
      { valor: "intermediario", rotulo: "Intermediário", descricao: "Já opero há algum tempo com alguma consistência", emoji: "📈" },
      { valor: "avancado", rotulo: "Avançado", descricao: "Tenho estratégias definidas e histórico positivo", emoji: "🎯" },
      { valor: "profissional", rotulo: "Profissional", descricao: "Trading é minha principal fonte de renda", emoji: "🏆" },
    ],
  },
  {
    id: 2,
    titulo: "Tempo Disponível",
    subtitulo: "Quanto tempo você dedica ao trading por dia?",
    icone: Clock,
    campo: "horas_dia",
    opcoes: [
      { valor: "1-2h", rotulo: "1 a 2 horas", descricao: "Acompanho o mercado no tempo livre", emoji: "⏱️" },
      { valor: "3-5h", rotulo: "3 a 5 horas", descricao: "Dedico uma boa parte do dia ao mercado", emoji: "🕐" },
      { valor: "6-8h", rotulo: "6 a 8 horas", descricao: "Trabalho sério, monitoro de perto", emoji: "💪" },
      { valor: "integral", rotulo: "Tempo integral", descricao: "Trading é meu trabalho principal", emoji: "🔥" },
    ],
  },
  {
    id: 3,
    titulo: "Apetite a Risco",
    subtitulo: "Qual é o seu perfil de tolerância ao risco?",
    icone: Shield,
    campo: "apetite_risco",
    opcoes: [
      { valor: "conservador", rotulo: "Conservador", descricao: "Prefiro retornos menores com mais segurança", emoji: "🛡️" },
      { valor: "moderado", rotulo: "Moderado", descricao: "Equilíbrio entre risco e retorno", emoji: "⚖️" },
      { valor: "agressivo", rotulo: "Agressivo", descricao: "Aceito riscos maiores por retornos expressivos", emoji: "⚡" },
      { valor: "insano", rotulo: "Insano 🔥", descricao: "All-in. Risco máximo, retorno máximo.", emoji: "💀" },
    ],
  },
  {
    id: 4,
    titulo: "Moedas Desejadas",
    subtitulo: "Quantas criptomoedas você quer monitorar?",
    icone: Coins,
    campo: "qtd_moedas",
    opcoes: [
      { valor: "3", rotulo: "3 moedas", descricao: "BTC, ETH e BNB — as principais do mercado", emoji: "🥉" },
      { valor: "10", rotulo: "10 moedas", descricao: "As top 10 por liquidez e volume", emoji: "🥈" },
      { valor: "20+", rotulo: "20+ moedas", descricao: "Cobertura completa de altcoins e DeFi", emoji: "🥇" },
    ],
  },
  {
    id: 5,
    titulo: "Alertas e Notificações",
    subtitulo: "Como você quer ser notificado sobre sinais?",
    icone: Bell,
    campo: "alertas_tipo",
    opcoes: [
      { valor: "nenhum", rotulo: "Sem alertas", descricao: "Vou acompanhar pelo dashboard", emoji: "👁️" },
      { valor: "navegador", rotulo: "Notificações no navegador", descricao: "Recebo alertas em tempo real no browser", emoji: "🔔" },
      { valor: "telegram", rotulo: "Alertas no Telegram", descricao: "Mensagens diretas no meu Telegram", emoji: "✈️" },
    ],
  },
]

// ============================================================
// COMPONENTE PRINCIPAL
// ============================================================

export default function OnboardingPage() {
  const router = useRouter()
  const supabase = criarClienteNavegador()

  const [etapaAtual, setEtapaAtual] = useState<number>(0)
  const [respostas, setRespostas] = useState<Partial<RespostasOnboarding>>({})
  const [salvando, setSalvando] = useState<boolean>(false)
  const [userId, setUserId] = useState<string | null>(null)

  // Pega o ID do usuário logado
  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) setUserId(data.user.id)
    })
  }, [supabase])

  const etapaConfig = ETAPAS[etapaAtual]
  const opcaoSelecionada = etapaConfig ? respostas[etapaConfig.campo] : null

  function selecionarOpcao(valor: string) {
    const campo = ETAPAS[etapaAtual].campo
    setRespostas((prev: Partial<RespostasOnboarding>) => ({ ...prev, [campo]: valor }))

    setTimeout(() => {
      if (etapaAtual < ETAPAS.length - 1) {
        setEtapaAtual((prev: number) => prev + 1)
      } else {
        setEtapaAtual(5)
      }
    }, 350)
  }

  function voltarEtapa() {
    if (etapaAtual > 0) {
      setEtapaAtual((prev: number) => prev - 1)
    }
  }

  async function confirmarPlano() {
  if (!userId || !respostas.nivel_experiencia) {
    console.error('❌ Dados faltando:', { userId, respostas })
    alert('Erro: Dados do usuário não encontrados. Faça login novamente.')
    return
  }
  
  setSalvando(true)

  try {
    console.log('📝 Salvando onboarding para:', userId)
    console.log('📋 Dados:', respostas)

    // Salvar tudo na tabela "perfis" (que já existe)
    const { data, error } = await supabase
      .from('perfis')
      .upsert({
        user_id: userId,
        nivel_experiencia: respostas.nivel_experiencia,
        horas_dia: respostas.horas_dia,
        apetite_risco: respostas.apetite_risco,
        qtd_moedas: respostas.qtd_moedas,
        alertas_tipo: respostas.alertas_tipo,
        onboarding_completo: true,
        plano: 'basico',
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (error) {
      console.error('❌ Erro ao salvar:', error)
      throw error
    }

    console.log('✅ Salvo com sucesso:', data)

    // Redirecionar para o dashboard
    router.push("/dashboard")
    router.refresh()
    
  } catch (err: any) {
    console.error('❌ Erro completo:', err)
    
    // Mensagem amigável baseada no tipo de erro
    if (err.code === '42501') {
      alert('Erro de permissão. Verifique as políticas de segurança (RLS).')
    } else if (err.code === '23505') {
      alert('Perfil já existe. Redirecionando...')
      router.push("/dashboard")
    } else {
      alert(`Erro ao salvar: ${err.message || 'Tente novamente.'}`)
    }
    
    setSalvando(false)
  }
}

  // Função para calcular plano recomendado localmente
  function calcularPlanoLocal(respostas: Partial<RespostasOnboarding>) {
    const pontuacao = {
      nivel_experiencia: { iniciante: 1, intermediario: 2, avancado: 3, profissional: 4 },
      horas_dia: { "1-2h": 1, "3-5h": 2, "6-8h": 3, integral: 4 },
      apetite_risco: { conservador: 1, moderado: 2, agressivo: 3, insano: 4 },
      qtd_moedas: { "3": 1, "10": 2, "20+": 3 },
      alertas_tipo: { nenhum: 1, navegador: 2, telegram: 3 },
    }

    const total =
      (pontuacao.nivel_experiencia[respostas.nivel_experiencia as keyof typeof pontuacao.nivel_experiencia] || 0) +
      (pontuacao.horas_dia[respostas.horas_dia as keyof typeof pontuacao.horas_dia] || 0) +
      (pontuacao.apetite_risco[respostas.apetite_risco as keyof typeof pontuacao.apetite_risco] || 0) +
      (pontuacao.qtd_moedas[respostas.qtd_moedas as keyof typeof pontuacao.qtd_moedas] || 0) +
      (pontuacao.alertas_tipo[respostas.alertas_tipo as keyof typeof pontuacao.alertas_tipo] || 0)

    if (total <= 8) return "basico"
    if (total <= 14) return "pro"
    return "enterprise"
  }

  // Função para obter rótulos localmente
  const getRotulo = (campo: string, valor: string): string => {
    const rotulos: Record<string, Record<string, string>> = {
      nivel_experiencia: {
        iniciante: "Iniciante",
        intermediario: "Intermediário",
        avancado: "Avançado",
        profissional: "Profissional",
      },
      horas_dia: {
        "1-2h": "1 a 2 horas por dia",
        "3-5h": "3 a 5 horas por dia",
        "6-8h": "6 a 8 horas por dia",
        integral: "Tempo integral",
      },
      apetite_risco: {
        conservador: "Conservador",
        moderado: "Moderado",
        agressivo: "Agressivo",
        insano: "Insano 🔥",
      },
      qtd_moedas: {
        "3": "3 moedas (Básico)",
        "10": "10 moedas (Pro)",
        "20+": "20+ moedas (Enterprise)",
      },
      alertas_tipo: {
        nenhum: "Sem alertas",
        navegador: "Alertas no navegador",
        telegram: "Alertas no Telegram",
      },
    }
    return rotulos[campo]?.[valor] || valor
  }

  // ──────────────────────────────────────────────────────────
  // TELA DE RESULTADO (etapa 5)
  // ──────────────────────────────────────────────────────────
  if (etapaAtual === 5) {
    const planoId = calcularPlanoLocal(respostas)
    const planoInfo = PLANOS[planoId as keyof typeof PLANOS]

    return (
      <div className="min-h-screen bg-[#080c14] flex flex-col items-center justify-center p-4">
        <div className="relative w-full max-w-lg">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-500/10 border border-cyan-500/30 mb-4">
              <CheckCircle2 className="w-8 h-8 text-cyan-400" />
            </div>
            <h2 className="text-2xl font-bold text-white">Seu plano ideal</h2>
            <p className="text-zinc-400 text-sm mt-1">
              Com base nas suas respostas, recomendamos:
            </p>
          </div>

          <div className="bg-zinc-900/80 border border-cyan-500/30 rounded-2xl p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-xs font-medium text-cyan-400 uppercase tracking-wider">
                  Recomendado para você
                </span>
                <h3 className="text-2xl font-bold text-white mt-0.5">
                  Plano {planoInfo.nome}
                </h3>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold text-cyan-400">
                  R$ {planoInfo.preco}
                </p>
                <p className="text-xs text-zinc-500">por mês</p>
              </div>
            </div>

            <div className="space-y-2">
              {[
                `${planoInfo.moedas} moedas monitoradas`,
                planoInfo.alertas ? "Alertas em tempo real" : "Dashboard com previsões",
                planoInfo.telegram ? "Alertas no Telegram incluídos" : "Sem alertas externos",
              ].map((beneficio, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <Check className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  <span className="text-zinc-300">{beneficio}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 mb-6">
            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Seu perfil</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {ETAPAS.map(etapa => {
                const resposta = respostas[etapa.campo] as string
                return (
                  <div key={etapa.id} className="flex items-center gap-2">
                    <etapa.icone className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                    <span className="text-zinc-500">{etapa.titulo}:</span>
                    <span className="text-zinc-300 font-medium">
                      {getRotulo(etapa.campo, resposta)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => router.push(`/checkout?plano=${planoId}`)}
              className="w-full flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-white font-semibold py-3 rounded-xl transition-all"
            >
              <Zap className="w-4 h-4" />
              Assinar Plano {planoInfo.nome} — R$ {planoInfo.preco}/mês
            </button>

            <button
              onClick={confirmarPlano}
              disabled={salvando}
              className="w-full flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium py-2.5 rounded-xl transition-all text-sm"
            >
              {salvando ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Salvando...</>
              ) : (
                "Continuar com o plano Básico gratuito →"
              )}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ──────────────────────────────────────────────────────────
  // TELAS DE PERGUNTAS (etapas 0–4)
  // ──────────────────────────────────────────────────────────
  if (!etapaConfig) return null

  const Icone = etapaConfig.icone

  return (
    <div className="min-h-screen bg-[#080c14] flex flex-col items-center justify-center p-4">
      <div className="relative w-full max-w-lg">
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600">
            <TrendingUp className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-white tracking-tight">TRADER AI</span>
        </div>

        <div className="mb-8">
          <div className="flex items-center justify-between text-xs text-zinc-500 mb-2">
            <span>Configurando seu perfil</span>
            <span>Etapa {etapaAtual + 1} de {ETAPAS.length}</span>
          </div>
          <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${((etapaAtual + 1) / ETAPAS.length) * 100}%` }}
            />
          </div>
        </div>

        <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
              <Icone className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">{etapaConfig.titulo}</h2>
              <p className="text-sm text-zinc-400">{etapaConfig.subtitulo}</p>
            </div>
          </div>

          <div className="space-y-3">
            {etapaConfig.opcoes.map(opcao => {
              const selecionada = opcaoSelecionada === opcao.valor
              return (
                <button
                  key={opcao.valor}
                  onClick={() => selecionarOpcao(opcao.valor)}
                  className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition-all duration-200 ${
                    selecionada
                      ? "border-cyan-500 bg-cyan-500/10 shadow-lg shadow-cyan-500/10"
                      : "border-zinc-700 bg-zinc-800/40 hover:border-zinc-600 hover:bg-zinc-800/70"
                  }`}
                >
                  <span className="text-2xl flex-shrink-0">{opcao.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-semibold text-sm ${selecionada ? "text-cyan-300" : "text-white"}`}>
                      {opcao.rotulo}
                    </p>
                    <p className="text-xs text-zinc-400 mt-0.5 truncate">{opcao.descricao}</p>
                  </div>
                  <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-all ${
                    selecionada ? "border-cyan-400 bg-cyan-400" : "border-zinc-600"
                  }`}>
                    {selecionada && <Check className="w-3 h-3 text-zinc-900" />}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center justify-between mt-6">
          <button
            onClick={voltarEtapa}
            disabled={etapaAtual === 0}
            className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Voltar
          </button>
          <p className="text-xs text-zinc-600">
            Selecione uma opção para continuar
          </p>
          <div className="w-16" />
        </div>
      </div>
    </div>
  )
}