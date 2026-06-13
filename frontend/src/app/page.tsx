'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { users } from '@/lib/api';
import type { UserCreate } from '@/lib/types';
import styles from './page.module.css';

const GOALS = [
  'ML research intern at top lab',
  'SWE intern at product company',
  'Data science intern (industry)',
  'AI/NLP research internship',
  'CV / robotics intern',
];

export default function LandingPage() {
  const router = useRouter();
  const [form, setForm] = useState<UserCreate>({ name: '', email: '', goal: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required'); return; }
    setLoading(true);
    setError('');
    try {
      const user = await users.create({ ...form, email: form.email || undefined, goal: form.goal || undefined });
      localStorage.setItem('mitra_user_id', user.id);
      localStorage.setItem('mitra_user_name', user.name);
      router.push('/chat');
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleReturn() {
    const id = localStorage.getItem('mitra_user_id');
    if (id) router.push('/chat');
  }

  const existingUser = typeof window !== 'undefined' && localStorage.getItem('mitra_user_id');

  return (
    <div className={styles.page}>
      {/* Grid backdrop */}
      <div className={styles.grid} aria-hidden />

      <div className={styles.center}>
        {/* Logo / hero */}
        <div className={styles.hero}>
          <div className={styles.hexWrap}>
            <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
              <polygon
                points="36,4 66,20 66,52 36,68 6,52 6,20"
                stroke="#4f8ef7"
                strokeWidth="1.5"
                fill="rgba(79,142,247,0.08)"
              />
              <polygon
                points="36,14 56,25 56,47 36,58 16,47 16,25"
                stroke="rgba(79,142,247,0.35)"
                strokeWidth="1"
                fill="none"
              />
              <text x="36" y="41" textAnchor="middle" fill="#4f8ef7" fontSize="18" fontFamily="JetBrains Mono,monospace" fontWeight="500">⬡</text>
            </svg>
          </div>
          <h1 className={styles.title}>mitra</h1>
          <p className={styles.subtitle}>Career Intelligence OS for ML/AI students</p>
          <div className={styles.chips}>
            <span className="badge badge-blue">Multi-Agent AI</span>
            <span className="badge badge-teal">Skill Gap Analysis</span>
            <span className="badge badge-muted">pgvector Memory</span>
          </div>
        </div>

        {/* Form card */}
        <div className={`${styles.formCard} card`}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>Initialize Session</span>
            <span className="badge badge-muted mono">new user</span>
          </div>

          <form onSubmit={handleCreate} className={styles.form}>
            <div className={styles.field}>
              <label className={styles.label}>Name</label>
              <input
                className="input"
                placeholder="e.g. Arjun Sharma"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                autoFocus
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Email <span className={styles.optional}>(optional)</span></label>
              <input
                className="input"
                type="email"
                placeholder="your@email.com"
                value={form.email ?? ''}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Primary Goal</label>
              <div className={styles.goalGrid}>
                {GOALS.map(g => (
                  <button
                    key={g}
                    type="button"
                    className={`${styles.goalChip} ${form.goal === g ? styles.goalChipActive : ''}`}
                    onClick={() => setForm(f => ({ ...f, goal: g }))}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <input
                className="input"
                style={{ marginTop: 'var(--s2)' }}
                placeholder="or type your own goal…"
                value={form.goal ?? ''}
                onChange={e => setForm(f => ({ ...f, goal: e.target.value }))}
              />
            </div>

            {error && <p className={styles.error}>{error}</p>}

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', justifyContent: 'center', padding: 'var(--s3)' }}>
              {loading ? <><span className="spinner" style={{width:14,height:14}} />Initializing…</> : '→ Launch Mitra'}
            </button>
          </form>
        </div>

        {existingUser && (
          <button onClick={handleReturn} className="btn btn-ghost" style={{ marginTop: 'var(--s4)' }}>
            ↩ Return to existing session
          </button>
        )}

        {/* Feature grid */}
        <div className={styles.features}>
          {[
            { icon: '⌬', title: 'Multi-Agent Chat', desc: '6 specialized agents: Opportunity Hunter, Gap Detector, Roadmap Planner, Interview Coach, and more.' },
            { icon: '◈', title: 'Skill Gap Analysis', desc: 'Upload your resume. Mitra maps your skills against 50+ curated ML/AI internship listings.' },
            { icon: '▦', title: 'Application Tracker', desc: 'Kanban board to track applications from wishlist to offer. Linked to opportunity metadata.' },
            { icon: '◎', title: 'Episodic Memory', desc: 'Mitra remembers your goals, past queries, and progress across sessions using pgvector.' },
          ].map(f => (
            <div key={f.title} className={`${styles.featureCard} card`}>
              <span className={styles.featureIcon}>{f.icon}</span>
              <h3 className={styles.featureTitle}>{f.title}</h3>
              <p className={styles.featureDesc}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
