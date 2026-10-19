'use client'

import Link from 'next/link'
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react'
import { useState } from 'react'

function AuthLoader() { return <span className="claude-loader" aria-label="Creating your account"><i /><i /><i /></span> }

function AuthSuccess({ onReset }: { onReset: () => void }) {
  return <div className="auth-success" role="status"><span className="success-mark">✓</span><h3>Account created</h3><p>Your account is ready. Start exploring historical knowledge in your workspace.</p><Link href="/workspace" className="auth-submit">Open workspace <ArrowRight data-icon="inline-end" /></Link><button type="button" className="auth-reset" onClick={onReset}>Create another account</button></div>
}

export default function SignUpPage() {
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => { e.preventDefault(); setLoading(true); window.setTimeout(() => { setLoading(false); setSuccess(true) }, 900) }
  return <main className="auth-shell"><div className="auth-visual signup-visual"><Link href="/" className="brand"><span className="brand-mark"><BookOpen /></span><span>Itihasa <em>AI</em></span></Link><div><div className="eyebrow accent-label">MAKE A CONNECTION</div><h1>Give your research more room to grow.</h1><p>Save questions, collect sources, and return to the threads that matter.</p></div><div className="auth-feature-list"><span>Cross-lingual discovery</span><span>Evidence you can inspect</span><span>A workspace for long-form research</span></div></div><section className="auth-panel"><Link href="/" className="back-link"><ArrowLeft data-icon="inline-start" /> Back to home</Link><div className="auth-form-wrap"><div className="eyebrow accent-label">GET STARTED</div><h2>Create your account</h2><p className="auth-intro">Join a quieter, deeper way to search the past.</p>{success ? <AuthSuccess onReset={() => setSuccess(false)} /> : <form onSubmit={handleSubmit}><label>Your name<input type="text" required placeholder="Your name" /></label><label>Email address<input type="email" required placeholder="you@example.com" /></label><label>Password<input type="password" minLength={8} required placeholder="At least 8 characters" /></label><button className="auth-submit" disabled={loading}>{loading ? <><AuthLoader /> Creating account</> : <>Create account <ArrowRight data-icon="inline-end" /></>}</button></form>}<p className="terms-copy">By continuing, you agree to our terms and understand how we handle your research.</p><p className="auth-switch">Already have an account? <Link href="/auth/sign-in">Sign in</Link></p></div></section></main>
}
