'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { profile } from '@/lib/api';
import type { SkillProfile } from '@/lib/types';
import styles from './page.module.css';

const SKILL_CATEGORIES: Record<string, string[]> = {
  'ML/DL': ['PyTorch', 'TensorFlow', 'scikit-learn', 'Keras', 'JAX', 'Hugging Face'],
  'Programming': ['Python', 'C++', 'JavaScript', 'R', 'SQL', 'Bash'],
  'MLOps': ['Docker', 'Kubernetes', 'MLflow', 'DVC', 'FastAPI', 'Git'],
  'Math': ['Linear Algebra', 'Statistics', 'Calculus', 'Probability', 'Optimization'],
  'NLP/CV': ['Transformers', 'BERT', 'GPT', 'OpenCV', 'CLIP', 'Diffusion Models'],
  'Cloud': ['AWS', 'GCP', 'Azure', 'Colab', 'Kaggle', 'HuggingFace Hub'],
};

export default function ProfilePage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [skillProfile, setSkillProfile] = useState<SkillProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const id = localStorage.getItem('mitra_user_id');
    if (!id) { router.push('/'); return; }
    setUserId(id);
    profile.get(id)
      .then(p => setSkillProfile(p))
      .catch(() => setSkillProfile(null))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !userId) return;
    setUploading(true);
    setError('');
    setSuccess('');
    try {
      const p = await profile.upload(userId, file);
      setSkillProfile(p);
      setSuccess(`Extracted ${p.raw_skills.length} skills from your resume.`);
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
    }
  }

  const skills = skillProfile?.raw_skills ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>Skill Profile</h1>
            <p className={styles.subtitle}>Upload your resume to extract and visualize your skills</p>
          </div>
          <div className={styles.headerActions}>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={handleUpload}
            />
            <button
              className="btn btn-primary"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? <><span className="spinner" />Analyzing…</> : '↑ Upload Resume (PDF)'}
            </button>
          </div>
        </div>

        {error && <div className={styles.alert} style={{ borderColor: 'rgba(255,71,87,0.3)', color: 'var(--red)', background: 'var(--red-dim)' }}>{error}</div>}
        {success && <div className={styles.alert} style={{ borderColor: 'rgba(0,212,170,0.3)', color: 'var(--teal)', background: 'var(--teal-dim)' }}>{success}</div>}

        <div className={styles.grid}>
          {/* Radar Chart */}
          <div className={`${styles.radarCard} card`}>
            <div className={styles.cardHeader}>
              <span className="section-label">Skill Radar</span>
              {skills.length > 0 && (
                <span className="badge badge-blue">{skills.length} skills</span>
              )}
            </div>
            {loading ? (
              <div className={styles.loadingCenter}><span className="spinner" /></div>
            ) : skills.length === 0 ? (
              <div className={styles.radarEmpty}>
                <span style={{ fontSize: 32, color: 'var(--text-muted)' }}>◎</span>
                <p>Upload your resume to see your skill radar</p>
              </div>
            ) : (
              <RadarChart skills={skills} categories={SKILL_CATEGORIES} />
            )}
          </div>

          {/* Skills by category */}
          <div className={`${styles.skillsCard} card`}>
            <div className={styles.cardHeader}>
              <span className="section-label">Detected Skills</span>
            </div>
            {loading ? (
              <div className={styles.loadingCenter}><span className="spinner" /></div>
            ) : skills.length === 0 ? (
              <div className={styles.emptySkills}>
                <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No skills detected yet.</p>
              </div>
            ) : (
              <div className={styles.categoryList}>
                {Object.entries(SKILL_CATEGORIES).map(([cat, catSkills]) => {
                  const matched = catSkills.filter(s =>
                    skills.some(sk => sk.toLowerCase().includes(s.toLowerCase()))
                  );
                  const extra = skills.filter(sk =>
                    !Object.values(SKILL_CATEGORIES).flat().some(s => sk.toLowerCase().includes(s.toLowerCase()))
                  );
                  if (matched.length === 0 && cat !== Object.keys(SKILL_CATEGORIES)[0]) return null;
                  return (
                    <div key={cat} className={styles.category}>
                      <span className={styles.categoryLabel}>{cat}</span>
                      <div className={styles.skillTags}>
                        {matched.map(s => (
                          <span key={s} className="badge badge-blue">{s}</span>
                        ))}
                        {matched.length === 0 && (
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>None detected</span>
                        )}
                      </div>
                      {cat === Object.keys(SKILL_CATEGORIES)[0] && extra.length > 0 && (
                        <>
                          <span className={styles.categoryLabel} style={{ marginTop: 'var(--s4)' }}>Other</span>
                          <div className={styles.skillTags}>
                            {extra.slice(0, 20).map(s => (
                              <span key={s} className="badge badge-muted">{s}</span>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function RadarChart({ skills, categories }: { skills: string[]; categories: Record<string, string[]> }) {
  const cx = 150, cy = 150, r = 110;
  const catNames = Object.keys(categories);
  const n = catNames.length;

  const scores = catNames.map(cat => {
    const catSkills = categories[cat];
    const matched = catSkills.filter(s =>
      skills.some(sk => sk.toLowerCase().includes(s.toLowerCase()))
    ).length;
    return Math.min(matched / catSkills.length, 1);
  });

  function point(angle: number, radius: number) {
    const a = angle - Math.PI / 2;
    return { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
  }

  const levels = [0.25, 0.5, 0.75, 1];
  const axes = catNames.map((_, i) => point((2 * Math.PI * i) / n, r));
  const dataPoints = scores.map((s, i) => point((2 * Math.PI * i) / n, s * r));
  const polyline = dataPoints.map(p => `${p.x},${p.y}`).join(' ');

  return (
    <div className={styles.radarWrap}>
      <svg viewBox="0 0 300 300" width="300" height="300" className={styles.radarSvg}>
        {/* Grid levels */}
        {levels.map(lv => {
          const pts = catNames.map((_, i) => point((2 * Math.PI * i) / n, lv * r));
          return (
            <polygon
              key={lv}
              points={pts.map(p => `${p.x},${p.y}`).join(' ')}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
            />
          );
        })}
        {/* Axes */}
        {axes.map((pt, i) => (
          <line key={i} x1={cx} y1={cy} x2={pt.x} y2={pt.y} stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
        ))}
        {/* Data polygon */}
        <polygon
          points={polyline}
          fill="rgba(79,142,247,0.15)"
          stroke="rgba(79,142,247,0.7)"
          strokeWidth="1.5"
        />
        {/* Data dots */}
        {dataPoints.map((pt, i) => (
          <circle key={i} cx={pt.x} cy={pt.y} r="3" fill="var(--blue)" />
        ))}
        {/* Labels */}
        {axes.map((pt, i) => {
          const label = catNames[i];
          const dx = pt.x > cx + 5 ? 8 : pt.x < cx - 5 ? -8 : 0;
          const dy = pt.y > cy + 5 ? 14 : pt.y < cy - 5 ? -8 : 4;
          return (
            <text
              key={i}
              x={pt.x + dx}
              y={pt.y + dy}
              textAnchor={pt.x > cx + 5 ? 'start' : pt.x < cx - 5 ? 'end' : 'middle'}
              fill="var(--text-secondary)"
              fontSize="10"
              fontFamily="JetBrains Mono, monospace"
            >
              {label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
