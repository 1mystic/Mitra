'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { profile } from '@/lib/api';
import { useRequireAuth } from '@/lib/useRequireAuth';
import type { ProfileUploadResponse } from '@/lib/types';
import styles from './page.module.css';

type Phase = 'upload' | 'processing' | 'done' | 'error';

const STAGES = [
  'Extracting text from PDF',
  'Identifying your skills',
  'Chunking & embedding for memory',
];

// Advance to stage 1 after 1.2s, stage 2 after another 2.5s.
// Stage 2 stays active until the server responds — it's the slow part.
const STAGE_DELAYS = [1200, 2500];

const TIPS = [
  'Mitra uses pgvector cosine similarity to match you to internships semantically, not just keyword search.',
  'Your resume is split into overlapping chunks so Mitra can recall specific sections mid-conversation.',
  'Skill matching uses a 80+ term taxonomy with fuzzy matching, so "pytorch" and "PyTorch" are treated the same.',
  'The more detailed your resume, the better Mitra can identify skill gaps vs. specific job requirements.',
  'Once set up, Mitra remembers every conversation and builds context across sessions.',
];

export default function OnboardingPage() {
  const router = useRouter();
  const userId = useRequireAuth();
  const fileRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>('upload');
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState(0);
  const [tipIdx, setTipIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<ProfileUploadResponse | null>(null);
  const [error, setError] = useState('');

  // Advance stages at realistic intervals matching actual backend work.
  useEffect(() => {
    if (phase !== 'processing') return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    STAGE_DELAYS.forEach((delay, i) => {
      let acc = 0;
      for (let j = 0; j <= i; j++) acc += STAGE_DELAYS[j] ?? 0;
      timers.push(setTimeout(() => setStage(i + 1), acc));
    });
    return () => timers.forEach(clearTimeout);
  }, [phase]);

  // Rotate tips every 4 seconds while processing.
  useEffect(() => {
    if (phase !== 'processing') return;
    const t = setInterval(() => setTipIdx(i => (i + 1) % TIPS.length), 4000);
    return () => clearInterval(t);
  }, [phase]);

  // Elapsed counter so users see the clock ticking — reduces abandon rate.
  useEffect(() => {
    if (phase !== 'processing') { setElapsed(0); return; }
    const t = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  async function processFile(file: File) {
    if (!userId) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file.');
      setPhase('error');
      return;
    }

    setPhase('processing');
    setStage(0);
    setError('');

    try {
      const res = await profile.upload(userId, file);
      setResult(res);
      setStage(STAGES.length - 1);
      setPhase('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase('error');
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  function handleSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }

  if (!userId) return null;

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.step}>Step 1 of 1 · Onboarding</div>

        {phase === 'upload' && (
          <>
            <h1 className={styles.title}>Upload your resume</h1>
            <p className={styles.sub}>
              Mitra reads your resume to map your skills, find matching internships, and
              ground every answer in your real experience. This takes about 15 seconds.
            </p>

            <input
              ref={fileRef}
              type="file"
              accept=".pdf,application/pdf"
              style={{ display: 'none' }}
              onChange={handleSelect}
            />
            <div
              className={`${styles.dropzone} ${dragging ? styles.dropzoneActive : ''}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <div className={styles.dropIcon}>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="18" x2="12" y2="12" />
                  <line x1="9" y1="15" x2="15" y2="15" />
                </svg>
              </div>
              <div className={styles.dropTitle}>Drop your PDF here or click to browse</div>
              <div className={styles.dropHint}>PDF only · max ~10 pages · text-based (not scanned)</div>
            </div>
          </>
        )}

        {phase === 'processing' && (
          <>
            <h1 className={styles.title}>Analysing your resume…</h1>
            <p className={styles.sub}>
              Building your semantic profile. Usually under 20 seconds.
              <span className={styles.elapsed}> {elapsed}s</span>
            </p>
            <div className={styles.stages}>
              {STAGES.map((label, i) => {
                const isDone = i < stage;
                const isActive = i === stage;
                return (
                  <div
                    key={label}
                    className={`${styles.stage} ${isActive ? styles.stageActive : ''} ${isDone ? styles.stageDone : ''}`}
                  >
                    <span className={styles.stageIcon}>
                      {isDone ? (
                        <svg className={styles.checkIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : isActive ? (
                        <span className="spinner spinner-sm spinner-accent" />
                      ) : (
                        <span className={styles.stageDot} />
                      )}
                    </span>
                    {label}
                  </div>
                );
              })}
            </div>
            <div className={styles.tip}>
              <span className={styles.tipLabel}>Did you know</span>
              {TIPS[tipIdx]}
            </div>
          </>
        )}

        {phase === 'done' && result && (
          <>
            <h1 className={styles.title}>You&apos;re all set!</h1>
            <p className={styles.sub}>
              Mitra now understands your profile and is ready to help you find and land an internship.
            </p>
            <div className={styles.resultStats}>
              <div className={styles.resultStat}>
                <span className={styles.resultStatVal}>{Object.keys(result.skills ?? {}).length}</span>
                <span className={styles.resultStatLabel}>Skills mapped</span>
              </div>
              <div className={styles.resultStat}>
                <span className={styles.resultStatVal}>{result.projects?.length ?? 0}</span>
                <span className={styles.resultStatLabel}>Projects found</span>
              </div>
              <div className={styles.resultStat}>
                <span className={styles.resultStatVal}>{result.chunk_count}</span>
                <span className={styles.resultStatLabel}>Memory chunks</span>
              </div>
            </div>
            <button className={styles.continueBtn} onClick={() => router.push('/chat')}>
              Start with Mitra →
            </button>
          </>
        )}

        {phase === 'error' && (
          <>
            <h1 className={styles.title}>Something went wrong</h1>
            <p className={styles.sub}>We couldn&apos;t process that file. Please try a different PDF.</p>
            <div className={styles.error}>{error}</div>
            <button className={styles.retryBtn} onClick={() => { setPhase('upload'); setError(''); }}>
              Try again
            </button>
          </>
        )}
      </div>
    </div>
  );
}
