'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { opportunities } from '@/lib/api';
import { getUserId } from '@/lib/auth';
import type { Opportunity } from '@/lib/types';
import styles from './page.module.css';

const TYPES = ['All', 'Research', 'SWE', 'Data Science', 'ML Engineering', 'Product'];

function matchBadge(score?: number) {
  if (!score) return { cls: 'badge-white', label: null };
  if (score >= 0.8) return { cls: 'badge-green', label: `${Math.round(score * 100)}% match` };
  if (score >= 0.5) return { cls: 'badge-accent', label: `${Math.round(score * 100)}% match` };
  return { cls: 'badge-amber', label: `${Math.round(score * 100)}% match` };
}

export default function OpportunitiesPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [items, setItems] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [typeFilter, setTypeFilter] = useState('All');
  const [error, setError] = useState('');

  useEffect(() => {
    const id = getUserId();
    if (!id) { router.replace('/auth'); return; }
    setUserId(id);
    fetchAll();
  }, [router]);

  async function fetchAll() {
    setLoading(true);
    try {
      const data = await opportunities.list(0, 50);
      setItems(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) { fetchAll(); return; }
    setSearching(true);
    setError('');
    try {
      const data = await opportunities.search({ query: searchQuery.trim(), user_id: userId ?? undefined, limit: 20 });
      setItems(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setSearching(false);
    }
  }

  const filtered = typeFilter === 'All'
    ? items
    : items.filter(o => o.type.toLowerCase().includes(typeFilter.toLowerCase()));

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>Internship Board</h1>
            <p className={styles.subtitle}>Curated ML/AI opportunities · Semantic search via pgvector</p>
          </div>
          <span className="badge badge-white">{filtered.length} listings</span>
        </div>

        <div className={styles.searchRow}>
          <div className={styles.searchWrap}>
            <span className={styles.searchIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </span>
            <input
              className={`field-input ${styles.searchInput}`}
              placeholder="Semantic search: PyTorch NLP research, Bangalore CV intern..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <button className="btn btn-white" onClick={handleSearch} disabled={searching || loading}>
            {searching ? <><span className="spinner spinner-sm" style={{ borderTopColor: '#000', borderColor: 'rgba(0,0,0,0.15)' }} />Searching</> : 'Search'}
          </button>
          {searchQuery && (
            <button className="btn btn-dark" onClick={() => { setSearchQuery(''); fetchAll(); }}>
              Clear
            </button>
          )}
        </div>

        <div className={styles.filters}>
          {TYPES.map(t => (
            <button
              key={t}
              className={`${styles.filterChip} ${typeFilter === t ? styles.filterActive : ''}`}
              onClick={() => setTypeFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>

        {error && <div className={styles.errMsg}>{error}</div>}

        {loading ? (
          <div className={styles.loadingGrid}>
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className={styles.skeleton} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ color: 'var(--text-3)' }}>
              <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6M9 12h6M9 15h4"/>
            </svg>
            <p>No listings found. Seed the database with <code style={{ fontSize: 12 }}>python -m db.seed_opportunities</code></p>
          </div>
        ) : (
          <div className={styles.grid}>
            {filtered.map(opp => {
              const mb = matchBadge(opp.match_score);
              return (
                <div key={opp.id} className={`${styles.oppCard} card`}>
                  <div className={styles.oppHead}>
                    <div className={styles.oppMeta}>
                      <span className={styles.oppCompany}>{opp.company}</span>
                      <span className={styles.oppDot} />
                      <span className={styles.oppLocation}>{opp.location}</span>
                    </div>
                    {mb.label && <span className={`badge ${mb.cls}`}>{mb.label}</span>}
                  </div>

                  <h3 className={styles.oppTitle}>{opp.title}</h3>

                  {opp.description && (
                    <p className={styles.oppDesc}>
                      {opp.description.slice(0, 180)}{opp.description.length > 180 ? '...' : ''}
                    </p>
                  )}

                  <div className={styles.oppSkills}>
                    {opp.skills_required.slice(0, 5).map(s => (
                      <span key={s} className={styles.oppSkillTag}>{s}</span>
                    ))}
                    {opp.skills_required.length > 5 && (
                      <span className={styles.oppSkillTag}>+{opp.skills_required.length - 5}</span>
                    )}
                  </div>

                  <div className={styles.oppFooter}>
                    <div className={styles.oppMeta2}>
                      {opp.stipend && <span className={styles.stipend}>{opp.stipend}</span>}
                      {opp.deadline && <span className={styles.deadline}>Due {opp.deadline}</span>}
                    </div>
                    {opp.url && (
                      <a
                        href={opp.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`btn btn-dark ${styles.applyBtn}`}
                      >
                        Apply
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M7 17L17 7M7 7h10v10"/>
                        </svg>
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
