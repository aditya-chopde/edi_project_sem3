'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react'

export default function SignInPage() {
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
          <p className="terms-copy">
            Authentication is not connected yet. Continue in testing mode to use the chat;
            no credentials are needed or collected.
          </p>
          <Link className="auth-submit" href="/workspace">
            Continue to workspace <ArrowRight data-icon="inline-end" />
          </Link>
          <p className="auth-switch">New to Itihasa? <Link href="/auth/sign-up">Create an account</Link></p>
        </div>
      </section>
    </main>
  )
}
