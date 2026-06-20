// ============================================================
// MIDDLEWARE DE PROTEÇÃO DE ROTAS
// Arquivo: middleware.ts (raiz do projeto, ao lado de app/)
//
// Lógica:
//   - Não logado → /login
//   - Logado + onboarding incompleto → /onboarding
//   - Logado + onboarding completo → acesso livre às rotas protegidas
// ============================================================

import { createServerClient } from "@supabase/ssr"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

// Rotas que NÃO precisam de autenticação
const ROTAS_PUBLICAS = ["/login", "/cadastro", "/recuperar-senha", "/nova-senha"]

// Rotas de API (não redirecionar)
const ROTAS_API = ["/api"]

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Ignora rotas de API, arquivos estáticos e public
  if (
    ROTAS_API.some(r => pathname.startsWith(r)) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.includes(".")
  ) {
    return NextResponse.next()
  }

  // Cria cliente Supabase com cookies da requisição
  let response = NextResponse.next({ request })
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          response = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // Verifica sessão
  const { data: { user } } = await supabase.auth.getUser()
  const estaLogado = !!user
  const ehRotaPublica = ROTAS_PUBLICAS.some(r => pathname.startsWith(r))

  // 1. Não logado tentando acessar rota protegida → redireciona para login
  if (!estaLogado && !ehRotaPublica) {
    const url = new URL("/login", request.url)
    url.searchParams.set("redirect", pathname)
    return NextResponse.redirect(url)
  }

  // 2. Logado tentando acessar página de login/cadastro → redireciona para dashboard
  if (estaLogado && ehRotaPublica) {
    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  // 3. Logado mas na raiz "/" → redireciona para dashboard
  if (estaLogado && pathname === "/") {
    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  // 4. Logado + rota protegida → verifica onboarding
  if (estaLogado && !ehRotaPublica && pathname !== "/onboarding") {
    const { data: perfil } = await supabase
      .from("perfis")  // ✅ CORRIGIDO
      .select("onboarding_completo")
      .eq("user_id", user.id)  // ✅ CORRIGIDO
      .single()

    if (perfil && !perfil.onboarding_completo) {
      return NextResponse.redirect(new URL("/onboarding", request.url))
    }
  }
  return response
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}