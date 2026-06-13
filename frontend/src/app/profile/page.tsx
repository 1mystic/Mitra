'use client';

import { useState, useEffect, useRef } from 'react';
import { profile, users, auth as authApi } from '@/lib/api';
import type { SkillProfile, User } from '@/lib/types';
import { useRequireAuth } from '@/lib/useRequireAuth';
import styles from './page.module.css';

const SKILL_CATEGORIES: Record<string, string[]> = {
  'ML / Deep Learning': ['PyTorch', 'TensorFlow', 'scikit-learn', 'Keras', 'JAX', 'Hugging Face', 'XGBoost'],
  'Programming':        ['Python', 'C++', 'JavaScript', 'TypeScript', 'R', 'SQL', 'Bash', 'Go'],
  'MLOps':              ['Docker', 'Kubernetes', 'MLflow', 'DVC', 'FastAPI', 'Git', 'GitHub Actions', 'Ray'],
  'Mathematics':        ['Linear Algebra', 'Statistics', 'Calculus', 'Probability', 'Optimization', 'Information Theory'],
  'NLP / Vision':       ['Transformers', 'BERT', 'GPT', 'LangChain', 'OpenCV', 'CLIP', 'Diffusion Models', 'YOLO'],
  'Cloud & Infra':      ['AWS', 'GCP', 'Azure', 'Colab', 'Kaggle', 'HuggingFace Hub', 'Weights & Biases'],
};

export default function ProfilePage() {
  const userId = useRequireAuth();
  const [skillProfile, setSkillProfile] = useState<SkillProfile | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Account settings edit state
  const [editName, setEditName] = useState('');
  const [editGoal, setEditGoal] = useState('');
  const [savingAccount, setSavingAccount] = useState(false);
  const [accountSuccess, setAccountSuccess] = useState('');

  useEffect(() => {
    if (!userId) return;
    profile.get(userId)
      .then(p => setSkillProfile(p))
      .catch(() => setSkillProfile(null))
      .finally(() => setLoading(false));

    authApi.me()
      .then(u => {
        setUser(u);
        setEditName(u.name ?? '');
        setEditGoal(u.goal ?? '');
      })
      .catch(() => {});
  }, [userId]);

  async function handleSaveAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!userId) return;
    setSavingAccount(true);
    setAccountSuccess('');
    try {
      const updated = await users.update(userId, { name: editName.trim(), goal: editGoal.trim() });
      setUser(updated);
      setAccountSuccess('Profile updated.');
      setTimeout(() => setAccountSuccess(''), 3000);
    } catch {
      // ignore
    } finally {
      setSavingAccount(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !userId) return;
    setUploading(true);
    setError('');
    setSuccess('');
    try {
      const p = await profile.upload(userId, file);
      setSkillProfile(p);
      const skillCount = Object.keys(p.skills ?? {}).length;
      setSuccess(`Extracted ${skillCount} skills and created ${p.chunk_count} resume chunks.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const skills = Object.keys(skillProfile?.skills ?? {});

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Skill Profile</h1>
          <p className={styles.subtitle}>Upload your resume to map your skills and unlock personalised gap analysis</p>
        </div>
        <div>
          <input ref={fileRef} type="file" accept=".pdf" style={{ display: 'none' }} onChange={handleUpload} />
          <button
            className="btn btn-white"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading
              ? <><span className="spinner spinner-sm" style={{ borderTopColor: '#000', borderColor: 'rgba(0,0,0,0.15)' }} />Analysing…</>
              : 'Upload Resume (PDF)'}
          </button>
        </div>
      </div>

      {error   && <div className={styles.alert} style={{ borderColor: 'rgba(239,68,68,0.25)', color: 'var(--red)', background: 'var(--red-dim)' }}>{error}</div>}
      {success && <div className={styles.alert} style={{ borderColor: 'rgba(63,185,80,0.25)', color: 'var(--green)', background: 'var(--green-dim)' }}>{success}</div>}

      {/* Account settings */}
      <section className={styles.accountSection}>
        <div className={styles.accountHead}>
          <h2 className={styles.sectionTitle}>Account Settings</h2>
          <p className={styles.sectionSub}>Update your display name and career goal</p>
        </div>
        <form className={styles.accountForm} onSubmit={handleSaveAccount}>
          <div className={styles.formGroup}>
            <label className={styles.label} htmlFor="editName">Display Name</label>
            <input
              id="editName"
              className={styles.input}
              type="text"
              value={editName}
              onChange={e => setEditName(e.target.value)}
              placeholder="Your name"
              maxLength={80}
            />
          </div>
          <div className={styles.formGroup}>
            <label className={styles.label} htmlFor="editGoal">Career Goal</label>
            <input
              id="editGoal"
              className={styles.input}
              type="text"
              value={editGoal}
              onChange={e => setEditGoal(e.target.value)}
              placeholder="e.g. ML internships in India"
              maxLength={200}
            />
          </div>
          <div className={styles.accountFooter}>
            {accountSuccess && <span className={styles.accountSuccessMsg}>{accountSuccess}</span>}
            <button
              type="submit"
              className="btn btn-white"
              disabled={savingAccount || !editName.trim()}
            >
              {savingAccount ? <><span className="spinner spinner-sm" style={{ borderTopColor: '#000', borderColor: 'rgba(0,0,0,0.15)' }} />Saving…</> : 'Save changes'}
            </button>
          </div>
        </form>
      </section>

      <div className={styles.grid}>
        {/* Radar */}
        <div className={`${styles.radarCard} card`}>
          <div className={styles.cardHead}>
            <span className={styles.cardTitle}>Skill Radar</span>
            {skills.length > 0 && <span className="badge badge-white">{skills.length} skills detected</span>}
          </div>
          {loading
            ? <div className={styles.loadingCenter}><span className="spinner" /></div>
            : skills.length === 0
              ? (
                <div className={styles.radarEmpty}>
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ color: 'var(--text-3)' }}>
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 2v10l4 2"/>
                  </svg>
                  <p>Upload your resume to see your skill radar</p>
                </div>
              )
              : <RadarChart skills={skills} categories={SKILL_CATEGORIES} />
          }
        </div>

        {/* Skills by category */}
        <div className={`${styles.skillsCard} card`}>
          <div className={styles.cardHead}>
            <span className={styles.cardTitle}>Skills by Category</span>
          </div>
          {loading
            ? <div className={styles.loadingCenter}><span className="spinner" /></div>
            : skills.length === 0
              ? <div className={styles.emptySkills}>No skills detected yet — upload a resume to get started.</div>
              : (
                <div className={styles.categoryList}>
                  {Object.entries(SKILL_CATEGORIES).map(([cat, catSkills]) => {
                    const matched = catSkills.filter(s =>
                      skills.some(sk => sk.toLowerCase().includes(s.toLowerCase()))
                    );
                    return (
                      <div key={cat} className={styles.category}>
                        <span className={styles.catLabel}>{cat}</span>
                        <div className={styles.skillTags}>
                          {catSkills.map(s => {
                            const isMatch = matched.includes(s);
                            return (
                              <span key={s} className={`${styles.skillTag} ${isMatch ? styles.skillTagMatched : ''}`}>
                                {s}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                  {/* Extra skills not in categories */}
                  {(() => {
                    const allCatSkills = Object.values(SKILL_CATEGORIES).flat();
                    const extra = skills.filter(sk =>
                      !allCatSkills.some(s => sk.toLowerCase().includes(s.toLowerCase()))
                    );
                    if (extra.length === 0) return null;
                    return (
                      <div className={styles.category}>
                        <span className={styles.catLabel}>Other</span>
                        <div className={styles.skillTags}>
                          {extra.slice(0, 20).map(s => (
                            <span key={s} className={`${styles.skillTag} ${styles.skillTagMatched}`}>{s}</span>
                          ))}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )
          }
        </div>
      </div>
    </div>
  );
}

function RadarChart({ skills, categories }: { skills: string[]; categories: Record<string, string[]> }) {
  const cx = 150, cy = 150, r = 105;
  const cats = Object.keys(categories);
  const n = cats.length;

  const scores = cats.map(cat => {
    const catSkills = categories[cat];
    const matched = catSkills.filter(s =>
      skills.some(sk => sk.toLowerCase().includes(s.toLowerCase()))
    ).length;
    return Math.min(matched / catSkills.length, 1);
  });

  function pt(angle: number, radius: number) {
    const a = angle - Math.PI / 2;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  }

  const levels = [0.25, 0.5, 0.75, 1];
  const axes  = cats.map((_, i) => pt((2 * Math.PI * i) / n, r));
  const data  = scores.map((s, i) => pt((2 * Math.PI * i) / n, Math.max(s * r, 6)));
  const poly  = data.map(p => `${p.x},${p.y}`).join(' ');

  return (
    <div className={styles.radarWrap}>
      <svg viewBox="0 0 300 300" width="300" height="300" className={styles.radarSvg}>
        {/* Grid */}
        {levels.map(lv => (
          <polygon
            key={lv}
            points={cats.map((_, i) => { const p = pt((2 * Math.PI * i) / n, lv * r); return `${p.x},${p.y}`; }).join(' ')}
            fill="none"
            stroke="rgba(255,255,255,0.07)"
            strokeWidth="1"
          />
        ))}
        {/* Axes */}
        {axes.map((p, i) => (
          <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
        ))}
        {/* Data */}
        <polygon points={poly} fill="rgba(79,142,247,0.12)" stroke="rgba(79,142,247,0.6)" strokeWidth="1.5" />
        {data.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3.5" fill="#4f8ef7" />
        ))}
        {/* Labels */}
        {axes.map((p, i) => {
          const dx = p.x > cx + 4 ? 10 : p.x < cx - 4 ? -10 : 0;
          const dy = p.y > cy + 4 ? 16 : p.y < cy - 4 ? -8 : 4;
          return (
            <text
              key={i}
              x={p.x + dx}
              y={p.y + dy}
              textAnchor={p.x > cx + 4 ? 'start' : p.x < cx - 4 ? 'end' : 'middle'}
              fill="#666"
              fontSize="9.5"
              fontFamily="Inter, sans-serif"
              fontWeight="500"
            >
              {cats[i].split(' ')[0]}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
