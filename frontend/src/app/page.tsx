'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/auth';
import Footer from './components/Footer';
import styles from './page.module.css';

const FEATURES = [
  {
    tag: 'AUTOMATED DISCOVERY',
    tagColor: 'sky' as const,
    title: 'Semantic Opportunity Search',
    desc: 'pgvector cosine similarity surfaces ML, NLP, CV and research internships matched to your actual skill profile, not keywords.',
    stat: '50+ curated listings',
    wide: true,
  },
  {
    tag: 'SKILL INTELLIGENCE',
    tagColor: 'iris' as const,
    title: 'Gap Detector',
    desc: 'Upload your resume once. Mitra maps your skills against every job requirement and tells you exactly what to learn next.',
    wide: false,
  },
  {
    tag: 'INTERVIEW PREP',
    tagColor: 'mint' as const,
    title: 'AI Interview Coach',
    desc: 'Practice ML system design and behavioural questions with a coach that knows your background and target roles.',
    wide: false,
  },
  {
    tag: 'MULTI-AGENT PIPELINE',
    tagColor: 'sky' as const,
    title: 'Episodic Memory',
    desc: 'Mitra remembers your goals, conversations, and skill growth across sessions. Every answer is grounded in your real context.',
    stat: '6 specialised agents',
    wide: true,
  },
];

const STATS = [
  { val: '6', label: 'AI agents' },
  { val: '50+', label: 'ML/AI listings' },
  { val: 'pgvector', label: 'Semantic memory' },
  { val: 'Claude 4', label: 'Powered by' },
];

export default function LandingPage() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => { setAuthed(isAuthenticated()); }, []);

  const go = () => router.push(authed ? '/chat' : '/auth');

  return (
    <div className={styles.page}>
      {/* Ambient glow spots */}
      <div className={`${styles.glowSpot} ${styles.glowSpotLeft}`} aria-hidden />
      <div className={`${styles.glowSpot} ${styles.glowSpotRight}`} aria-hidden />

      {/* Hero */}
      <section className={styles.hero}>
        <h1 className={`${styles.heroTitle} display-1`}>
          Your Career<br />
          <span className="heading-gradient">Intelligence OS</span>
        </h1>

        <p className={`${styles.heroSub} body-lg`}>
          Mitra finds ML internships, maps your skill gaps, builds roadmaps, and coaches you for interviews. All through one persistent agentic system.
        </p>

        <div className={styles.heroActions}>
          <button className={`btn btn-primary ${styles.heroCta}`} onClick={go}>
            {authed ? 'Go to dashboard' : 'Deploy your agent'}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
          <a href="#features" className="btn btn-dark">
            See how it works
          </a>
        </div>

        {/* Stats bar */}
        <div className={styles.statsBar}>
          {STATS.map(s => (
            <div key={s.label} className={styles.stat}>
              <span className={styles.statVal}>{s.val}</span>
              <span className={styles.statLabel}>{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Bento feature grid */}
      <section id="features" className={styles.features}>
        <div className={styles.featuresHead}>
          <span className={`eyebrow ${styles.featuresEyebrow}`}>Capabilities</span>
          <h2 className={`display-2 ${styles.featuresTitle}`}>
            Everything you need, built natively.
          </h2>
          <p className="body-md" style={{ maxWidth: 440 }}>
            No generic AI layers. Individual micro-agents designed specifically for ML/AI internship pipelines.
          </p>
        </div>

        <div className={styles.bentoGrid}>
          {FEATURES.map(f => (
            <div
              key={f.title}
              className={`${styles.bentoCard} ${f.wide ? styles.bentoWide : ''}`}
              data-tag-color={f.tagColor}
            >
              <div className={`${styles.bentoGlow} ${styles[`glowColor_${f.tagColor}`]}`} aria-hidden />
              <span className={`${styles.bentoTag} ${styles[`tagColor_${f.tagColor}`]}`}>{f.tag}</span>
              <h3 className={styles.bentoTitle}>{f.title}</h3>
              <p className={styles.bentoDesc}>{f.desc}</p>
              {f.stat && (
                <div className={styles.bentoStat}>
                  <span className={styles.bentoStatVal}>{f.stat}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section id="get-started" className={styles.ctaSection}>
        <div className={styles.ctaCard}>
          <div className={styles.ctaGlow} aria-hidden />

          {/* Left column */}
          <div className={styles.ctaLeft}>
            <span className="eyebrow" style={{ color: 'var(--sky)' }}>GET STARTED</span>
            <h2 className={`${styles.ctaTitle} display-2`}>Ready in<br />under a minute</h2>
            <p className="body-md">
              Create your account, upload your resume, and Mitra builds your semantic profile. It remembers everything.
            </p>
            <button className={`btn btn-primary ${styles.ctaBtn}`} onClick={go}>
              {authed ? 'Go to dashboard' : 'Create your account'}
            </button>
          </div>

          {/* Right column */}
          <div className={styles.ctaRight}>
            {[
              { n: '01', t: 'Create your account', d: 'Email + password, 10 seconds.' },
              { n: '02', t: 'Upload your resume', d: 'Mitra maps your skills & builds episodic memory.' },
              { n: '03', t: 'Start the conversation', d: 'Find internships, close gaps, prep for interviews.' },
            ].map(s => (
              <div key={s.n} className={styles.step}>
                <span className={styles.stepNum}>{s.n}</span>
                <div>
                  <div className={styles.stepTitle}>{s.t}</div>
                  <div className={styles.stepDesc}>{s.d}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
