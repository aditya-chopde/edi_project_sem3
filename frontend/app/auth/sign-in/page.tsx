'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen, Mail } from 'lucide-react'
import { useState } from 'react'

const authUnavailable =
  'Sign-in is not available because the connected backend does not expose authentication endpoints. Your credentials were not sent.'

export default function SignInPage() {
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(authUnavailable)
  }

  return (
    <main className="auth-shell">
      <div className="auth-visual">
        <Link href="/" className="brand">
          <span className="brand-mark"><BookOpen /></span>
          <span>Itihasa <em>AI</em></span>
        </Link>
        <div>
          <div className="eyebrow accent-label">RETURN TO THE ARCHIVE</div>
          <h1>Your next question starts here.</h1>
          <p>Continue exploring historical knowledge across languages, scripts, and centuries.</p>
        </div>
        <span className="auth-caption">“The past is not behind us. It is beneath us.”</span>
      </div>
      <section className="auth-panel">
        <Link href="/" className="back-link"><ArrowLeft data-icon="inline-start" /> Back to home</Link>
        <div className="auth-form-wrap">
          <div className="eyebrow accent-label">WELCOME BACK</div>
          <h2>Sign in to Itihasa</h2>
          <p className="auth-intro">Pick up your research where you left off.</p>
          {error && <p className="auth-api-error" role="alert">{error}</p>}
          <form onSubmit={handleSubmit}>
            <label>
              Email address
              <input autoComplete="email" type="email" required placeholder="you@example.com" />
            </label>
            <label>
              Password
              <input autoComplete="current-password" type="password" required placeholder="Enter your password" />
            </label>
            <div className="form-row">
              <label className="check-label"><input type="checkbox" /> Remember me</label>
              <button className="auth-inline-button" onClick={() => setError(authUnavailable)} type="button">
                Forgot password?
              </button>
            </div>
            <button className="auth-submit" type="submit">
              Sign in <ArrowRight data-icon="inline-end" />
            </button>
          </form>
          <div className="auth-divider"><span>or</span></div>
          <button className="email-button" onClick={() => setError(authUnavailable)} type="button">
            <Mail data-icon="inline-start" /> Continue with email link
          </button>
          <p className="terms-copy">Authentication is not configured for this backend; no credentials are transmitted.</p>
          <p className="auth-switch">You can still <Link href="/workspace">continue to the workspace</Link>.</p>
          <p className="auth-switch">New to Itihasa? <Link href="/auth/sign-up">Create an account</Link></p>
        </div>
      </section>
    </main>
  )
}
