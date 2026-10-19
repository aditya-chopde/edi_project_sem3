'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen, Mail } from 'lucide-react'
import { useState } from 'react'

function AuthLoader() { return <span className="claude-loader" aria-label="Signing you in"><i /><i /><i /></span> }

function AuthSuccess({ onReset }: { onReset: () => void }) {
  return <div className="auth-success" role="status"><span className="success-mark">✓</span><h3>You&apos;re signed in</h3><p>Your account is ready to explore. Your research workspace is waiting.</p><Link href="/workspace" className="auth-submit">Open workspace <ArrowRight data-icon="inline-end" /></Link><button type="button" className="auth-reset" onClick={onReset}>Use another account</button></div>
}

export default function SignInPage() {
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => { e.preventDefault(); setLoading(true); window.setTimeout(() => { setLoading(false); setSuccess(true) }, 900) }
  return <main className="auth-shell"><div className="auth-visual"><Link href="/" className="brand"><span className="brand-mark"><BookOpen /></span><span>Itihasa <em>AI</em></span></Link><div><div className="eyebrow accent-label">RETURN TO THE ARCHIVE</div><h1>Your next question starts here.</h1><p>Continue exploring historical knowledge across languages, scripts, and centuries.</p></div><span className="auth-caption">“The past is not behind us. It is beneath us.”</span></div><section className="auth-panel"><Link href="/" className="back-link"><ArrowLeft data-icon="inline-start" /> Back to home</Link><div className="auth-form-wrap"><div className="eyebrow accent-label">WELCOME BACK</div><h2>Sign in to Itihasa</h2><p className="auth-intro">Pick up your research where you left off.</p>{success ? <AuthSuccess onReset={() => setSuccess(false)} /> : <form onSubmit={handleSubmit}><label>Email address<input type="email" required placeholder="you@example.com" /></label><label>Password<input type="password" required placeholder="Enter your password" /></label><div className="form-row"><label className="check-label"><input type="checkbox" /> Remember me</label><a href="#forgot">Forgot password?</a></div><button className="auth-submit" disabled={loading}>{loading ? <><AuthLoader /> Signing in</> : <>Sign in <ArrowRight data-icon="inline-end" /></>}</button></form>}<div className="auth-divider"><span>or</span></div><button className="email-button"><Mail data-icon="inline-start" /> Continue with email link</button><p className="auth-switch">New to Itihasa? <Link href="/auth/sign-up">Create an account</Link></p></div></section></main>
}
