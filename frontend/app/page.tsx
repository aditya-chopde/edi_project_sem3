"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  LoaderCircle,
  Menu,
  Sparkles,
} from "lucide-react";
import { api, type ApiDocument, type ApiHealth } from "@/lib/api";

export default function LandingPage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [documents, setDocuments] = useState<ApiDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([api.health(controller.signal), api.listDocuments(controller.signal)])
      .then(([apiHealth, apiDocuments]) => {
        setHealth(apiHealth);
        setDocuments(apiDocuments);
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load live archive status.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const readyDocuments = documents.filter((document) => document.status === "indexed");
  const languages = [...new Set(readyDocuments.map((document) => document.language))]
    .filter((language) => language && language !== "unknown")
    .slice(0, 3);

  return (
    <main className="landing-shell">
      <nav className="landing-nav">
        <Link href="/" className="brand">
          <span className="brand-mark"><BookOpen /></span>
          <span>Itihasa <em>AI</em></span>
        </Link>
        <div className={`landing-links ${menuOpen ? "is-open" : ""}`}>
          <a href="#why" onClick={() => setMenuOpen(false)}>Why Itihasa</a>
          <a href="#how" onClick={() => setMenuOpen(false)}>How it works</a>
          <Link href="/auth/sign-in" onClick={() => setMenuOpen(false)}>Sign in</Link>
          <Link href="/auth/sign-up" className="nav-cta" onClick={() => setMenuOpen(false)}>
            Start researching <ArrowRight data-icon="inline-end" />
          </Link>
        </div>
        <button
          aria-expanded={menuOpen}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          className="landing-menu"
          onClick={() => setMenuOpen((open) => !open)}
          type="button"
        >
          <Menu />
        </button>
      </nav>

      <section className="hero-section">
        <div className="hero-copy">
          <div className="eyebrow accent-label">A NEW LENS ON THE PAST</div>
          <h1>Research India&apos;s past, <span>across every language.</span></h1>
          <p className="hero-lede">
            Itihasa helps you find, understand, and connect historical knowledge
            across Sanskrit, Marathi, Persian, and the many voices of the subcontinent.
          </p>
          <div className="hero-actions">
            <Link href="/workspace" className="primary-cta">
              Begin your research <ArrowRight data-icon="inline-end" />
            </Link>
            <Link href="/workspace" className="secondary-cta">Explore the workspace</Link>
          </div>
          <div className="hero-proof">
            <span><Check data-icon="inline-start" /> Evidence-grounded answers</span>
            <span><Check data-icon="inline-start" /> Cross-lingual search</span>
          </div>
        </div>

        <div className="hero-card hero-breathing">
          <div className="hero-card-top">
            <span className="eyebrow">LIVE ARCHIVE</span>
            <span className={`live-pill ${error ? "is-offline" : ""}`}>
              <i /> {loading ? "Connecting" : error ? "Offline" : "Connected"}
            </span>
          </div>
          <div className="hero-question">
            <span className="question-label">Indexed documents</span>
            <p>
              {loading
                ? "Checking the connected archive…"
                : `${readyDocuments.length.toLocaleString()} of ${documents.length.toLocaleString()} documents are ready for search.`}
            </p>
          </div>
          <div className="hero-answer">
            <div className="answer-avatar"><Sparkles /></div>
            <div>
              <span className="question-label">Itihasa API</span>
              <p>
                {error ??
                  (loading
                    ? "Loading live index health…"
                    : health
                      ? `${health.sparse_docs.toLocaleString()} indexed passages are available for hybrid retrieval.`
                      : "The archive status is currently unavailable.")}
              </p>
              <div className="answer-loading">
                {loading ? (
                  <LoaderCircle aria-label="Loading archive status" className="landing-spinner" size={13} />
                ) : (
                  <i />
                )}
                <span>
                  {loading
                    ? "Loading live status"
                    : error
                      ? "Check backend connection"
                      : "Live backend status"}
                </span>
              </div>
            </div>
          </div>
          <div className="source-row">
            {languages.length ? languages.map((language) => (
              <span className="source-chip" key={language}>{language}</span>
            )) : <span className="source-chip">{readyDocuments.length ? "Language unspecified" : "No indexed sources"}</span>}
            <span className="source-count">
              {health ? `${health.dense_vectors.toLocaleString()} vectors` : "Archive"}
            </span>
          </div>
        </div>
      </section>

      <section id="why" className="trust-strip">
        <div>
          <span className="eyebrow">BUILT FOR DEEP READING</span>
          <h2>From scattered records to a connected history.</h2>
        </div>
        <p>
          Search beyond translations. Keep the original language, inspect the
          evidence, and follow ideas across time and place.
        </p>
      </section>

      <section id="how" className="feature-grid">
        <article>
          <span className="feature-number">01</span>
          <h3>Ask naturally</h3>
          <p>Write questions the way you think about them. Itihasa searches across languages and scripts without making you build the query first.</p>
        </article>
        <article>
          <span className="feature-number">02</span>
          <h3>See the evidence</h3>
          <p>Every answer points back to the documents that shaped it, so interpretation stays connected to the source.</p>
        </article>
        <article>
          <span className="feature-number">03</span>
          <h3>Build new connections</h3>
          <p>Compare traditions, follow recurring ideas, and surface relationships that are easy to miss in one archive.</p>
        </article>
      </section>

      <footer className="landing-footer">
        <span className="brand">
          <span className="brand-mark"><BookOpen /></span>
          <span>Itihasa <em>AI</em></span>
        </span>
        <span>Historical knowledge, made more discoverable.</span>
        <Link href="/workspace">Explore your documents <ArrowRight data-icon="inline-end" /></Link>
      </footer>
    </main>
  );
}
