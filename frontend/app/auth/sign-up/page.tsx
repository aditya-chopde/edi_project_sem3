'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react'
import { useState } from 'react'

const authUnavailable =
  'Account creation is not available because the connected backend does not expose authentication endpoints. Your details were not sent.'

export default function SignUpPage() {
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(authUnavailable)
  }

  return (
    <main className="auth-shell">
      <div className="auth-visual signup-visual">
        <Link href="/" className="brand">
          <span className="brand-mark"><BookOpen /></span>
          <span>Itihasa <em>AI</em></span>
        </Link>
        <div>
          <div className="eyebrow accent-label">MAKE A CONNECTION</div>
          <h1>Give your research more room to grow.</h1>
          <p>Save questions, collect sources, and return to the threads that matter.</p>
        </div>
        <div className="auth-feature-list">
          <span>Cross-lingual discovery</span>
          <span>Evidence you can inspect</span>
          <span>A workspace for long-form research</span>
        </div>
      </div>
      <section className="auth-panel">
        <Link href="/" className="back-link"><ArrowLeft data-icon="inline-start" /> Back to home</Link>
        <div className="auth-form-wrap">
          <div className="eyebrow accent-label">GET STARTED</div>
          <h2>Create your account</h2>
          <p className="auth-intro">Join a quieter, deeper way to search the past.</p>
          {error && <p className="auth-api-error" role="alert">{error}</p>}
          <form onSubmit={handleSubmit}>
            <label>
              Your name
              <input autoComplete="name" type="text" required placeholder="Your name" />
            </label>
            <label>
              Email address
              <input autoComplete="email" type="email" required placeholder="you@example.com" />
            </label>
            <label>
              Password
              <input autoComplete="new-password" type="password" minLength={8} required placeholder="At least 8 characters" />
            </label>
            <button className="auth-submit" type="submit">
              Create account <ArrowRight data-icon="inline-end" />
            </button>
          </form>
          <p className="terms-copy">Authentication is not configured for this backend; no account details are transmitted.</p>
          <p className="auth-switch">You can still <Link href="/workspace">continue to the workspace</Link>.</p>
          <p className="auth-switch">Already have an account? <Link href="/auth/sign-in">Sign in</Link></p>
        </div>
      </section>
    </main>
  )
}
