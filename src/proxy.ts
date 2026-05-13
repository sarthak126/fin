import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextFetchEvent, NextRequest, NextResponse } from 'next/server'

const authFeatureEnabled =
  process.env.NEXT_PUBLIC_ENABLE_AUTH?.trim().toLowerCase() !== 'false'
const hasRequiredClerkConfig =
  Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) &&
  Boolean(process.env.CLERK_SECRET_KEY)
const e2eAuthBypassEnabled =
  process.env.CODEX_E2E_AUTH_BYPASS?.trim().toLowerCase() === 'true'
const localAuthDisabledBypassEnabled =
  process.env.NODE_ENV !== 'production' && !authFeatureEnabled

const isProtectedRoute = createRouteMatcher(['/dashboard(.*)', '/reports(.*)'])

const clerkProxy = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect()
  }

  return NextResponse.next()
})

export default function proxy(req: NextRequest, event: NextFetchEvent) {
  if (localAuthDisabledBypassEnabled && isProtectedRoute(req)) {
    const response = NextResponse.next()
    response.cookies.set('codex-e2e-auth-bypass', 'true', {
      path: '/',
      sameSite: 'lax',
    })
    return response
  }

  if (
    e2eAuthBypassEnabled &&
    isProtectedRoute(req) &&
    req.cookies.get('codex-e2e-auth-bypass')?.value === 'true'
  ) {
    return NextResponse.next()
  }

  if (!authFeatureEnabled || !hasRequiredClerkConfig) {
    if (isProtectedRoute(req)) {
      return NextResponse.json(
        { error: 'Authentication is not configured for protected routes.' },
        { status: 503 }
      )
    }

    return NextResponse.next()
  }

  return clerkProxy(req, event)
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
