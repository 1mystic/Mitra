'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/auth';
import styles from './page.module.css';

export default function LandingPage() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  function goStart() {
    router.push(authed ? '/chat' : '/auth');
  }

  return (
    <div className={styles.page}>
      {/* Spotlight stage light */}
      <div className={styles.spotlight} aria-hidden />

      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.heroBadge}>
          <span className={styles.heroBadgeDot} />
          Multi-Agent AI for ML/AI Students in India
        </div>

        <h1 className={`${styles.heroTitle} display-1`}>
          Your Career<br />Intelligence OS
        </h1>

        <p className={`${styles.heroSub} body-lg`}>
          Mitra finds internships, maps skill gaps, builds roadmaps, and preps you for interviews — all through one conversational interface.
        </p>

        <div className={styles.heroActions}>
          <button className="btn btn-white" onClick={goStart}>
            {authed ? 'Go to dashboard' : 'Get started free'}
          </button>
          <a href="#get-started" className="btn btn-dark">
            See how it works
          </a>
        </div>

        {/* Mini stats */}
        <div className={styles.stats}>
          {[
            { val: '6', label: 'AI agents' },
            { val: '50+', label: 'Curated ML/AI listings' },
            { val: 'pgvector', label: 'Semantic memory' },
            { val: 'Claude 4', label: 'Powered by' },
          ].map(s => (
            <div key={s.label} className={styles.stat}>
              <span className={styles.statVal}>{s.val}</span>
              <span className={styles.statLabel}>{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Feature section */}
      <section className={styles.features}>
        <div className={styles.featuresHead}>
          <h2 className={`display-2 ${styles.featuresTitle}`}>Everything you need to land an ML internship</h2>
          <p className="body-md" style={{ maxWidth: 420 }}>
            Mitra connects your resume, goals, and the job market into one intelligent system that grows with you.
          </p>
        </div>

        <div className={styles.featureGrid}>
          {[
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
              ),
              title: 'Opportunity Hunter',
              desc: 'Semantic search across 50+ curated ML, NLP, CV, and research internships, matched to your skill profile.',
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
                </svg>
              ),
              title: 'Skill Gap Detector',
              desc: 'Upload your resume. Mitra maps your skills against job requirements and prioritizes what to learn next.',
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M3 3h18v18H3z"/><path d="M3 9h18M9 21V9"/>
                </svg>
              ),
              title: 'Roadmap Planner',
              desc: 'Get a week-by-week learning plan built around your timeline, current skills, and target role.',
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                </svg>
              ),
              title: 'Interview Coach',
              desc: 'Practice ML system design and behavioural questions with a coach that knows your background.',
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
                </svg>
              ),
              title: 'Application Tracker',
              desc: 'Kanban board that tracks every application from wishlist to offer, linked to opportunity metadata.',
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 2a10 10 0 100 20A10 10 0 0012 2z"/><path d="M12 6v6l4 2"/>
                </svg>
              ),
              title: 'Episodic Memory',
              desc: 'Mitra remembers your goals, past conversations, and skill progress across sessions using pgvector.',
            },
          ].map(f => (
            <div key={f.title} className={`${styles.featureCard} card`}>
              <div className={styles.featureIconWrap}>
                {f.icon}
              </div>
              <h3 className={styles.featureCardTitle}>{f.title}</h3>
              <p className={`${styles.featureCardDesc} body-sm`}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section id="get-started" className={styles.formSection}>
        <div className={styles.formCard}>
          <div className={styles.formCardHead}>
            <h2 className={styles.formCardTitle}>Get started in under a minute</h2>
            <p className={`body-sm ${styles.formCardSub}`}>
              Create your account, upload your resume once, and Mitra remembers everything across sessions.
            </p>
          </div>

          <div className={styles.ctaSteps}>
            {[
              { n: '1', t: 'Create your account', d: 'Email and password — takes 10 seconds.' },
              { n: '2', t: 'Upload your resume', d: 'Mitra maps your skills and builds your memory.' },
              { n: '3', t: 'Start the conversation', d: 'Find internships, close skill gaps, prep interviews.' },
            ].map(s => (
              <div key={s.n} className={styles.ctaStep}>
                <span className={styles.ctaStepNum}>{s.n}</span>
                <div>
                  <div className={styles.ctaStepTitle}>{s.t}</div>
                  <div className={styles.ctaStepDesc}>{s.d}</div>
                </div>
              </div>
            ))}
          </div>

          <button className={`btn btn-white ${styles.submitBtn}`} onClick={goStart}>
            {authed ? 'Go to dashboard' : 'Create your account'}
          </button>
        </div>
      </section>
    </div>
  );
}
