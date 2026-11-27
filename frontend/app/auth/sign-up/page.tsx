'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react'

export default function SignUpPage() {
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
          <p className="terms-copy">
            Account creation is not connected yet. You can still use the chat in testing
            mode; no account details are needed or collected.
          </p>
          <Link className="auth-submit" href="/workspace">
            Continue to workspace <ArrowRight data-icon="inline-end" />
          </Link>
          <p className="auth-switch">Already have an account? <Link href="/auth/sign-in">Sign in</Link></p>
        </div>
      </section>
    </main>
  )
}
