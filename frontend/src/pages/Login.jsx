import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const keyframes = `
@keyframes loginSlideUp {
  from { opacity:0; transform: translateY(24px); }
  to   { opacity:1; transform: translateY(0); }
}
`

export default function Login() {
  const [params] = useSearchParams()
  const hasError = params.get('error')

  return (
    <div style={{
      fontFamily: "'Inter', -apple-system, system-ui, sans-serif",
      background: '#ffffff', minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <style>{keyframes}</style>

      {/* Card */}
      <div style={{
        background: '#ffffff',
        borderRadius: 20,
        padding: '48px 40px 40px',
        width: '100%', maxWidth: 420,
        boxShadow: 'rgba(0,0,0,0.02) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 6px, rgba(0,0,0,0.1) 0px 4px 8px',
        animation: 'loginSlideUp .5s cubic-bezier(.4,0,.2,1) forwards',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 14,
            background: 'linear-gradient(135deg, #ff385c, #e00b41)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, boxShadow: '0 4px 14px rgba(255,56,92,.25)',
          }}>&#128062;</div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#222222', letterSpacing: '-0.4px' }}>NEU Assistant</div>
            <div style={{ fontSize: 12, color: '#6a6a6a', marginTop: 1 }}>Northeastern University</div>
          </div>
        </div>

        <h1 style={{ fontSize: 26, fontWeight: 700, color: '#222222', letterSpacing: '-0.4px', marginBottom: 6 }}>
          Welcome back
        </h1>
        <p style={{ fontSize: 14, color: '#6a6a6a', marginBottom: 32, lineHeight: 1.6 }}>
          Sign in to save your conversations and access live campus data.
        </p>

        {hasError && (
          <div style={{
            background: '#fef2f2', border: '1px solid #fecaca',
            color: '#c13515', fontSize: 13, padding: '10px 14px',
            borderRadius: 8, marginBottom: 20,
          }}>
            Sign-in failed. Please try again or use a different provider.
          </div>
        )}

        {/* Google OAuth */}
        <a
          href="/auth/google"
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            width: '100%', padding: '14px 18px',
            background: '#fff',
            border: '1px solid #dddddd',
            borderRadius: 8, fontSize: 14, fontWeight: 500, color: '#222222',
            textDecoration: 'none', marginBottom: 10,
            boxShadow: '0 1px 2px rgba(0,0,0,.04)',
            transition: 'all .18s cubic-bezier(.4,0,.2,1)',
          }}
          onMouseEnter={e => { e.currentTarget.style.boxShadow = 'rgba(0,0,0,0.08) 0px 4px 12px'; e.currentTarget.style.transform = 'translateY(-1px)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,.04)'; e.currentTarget.style.transform = 'translateY(0)' }}
        >
          <svg width="20" height="20" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.35-8.16 2.35-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          <span style={{ flex: 1, textAlign: 'center' }}>Continue with Google</span>
        </a>

        <div style={{ textAlign: 'center', fontSize: 12, color: '#6a6a6a', marginTop: 28, lineHeight: 1.6 }}>
          By signing in you agree to our{' '}
          <a href="#" style={{ color: '#222222', textDecoration: 'underline' }}>Terms of Service</a> and{' '}
          <a href="#" style={{ color: '#222222', textDecoration: 'underline' }}>Privacy Policy</a>.<br/>
          Your chats are saved securely and private to your account.
        </div>
      </div>
    </div>
  )
}
