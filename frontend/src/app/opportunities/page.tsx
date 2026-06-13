'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { opportunities } from '@/lib/api';
import type { Opportunity } from '@/lib/types';
import styles from './page.module.css';

const TYPES = ['All', 'Research', 'SWE', 'Data Science', 'ML Engineering', 'Product'];

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
    const id = localStorage.getItem('mitra_user_id');
    if (!id) { router.push('/'); return; }
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

  const matchColor = (score?: number) => {
    if (!score) return 'badge-muted';
    if (score >= 0.8) return 'badge-teal';
    if (score >= 0.5) return 'badge-blue';
    return 'badge-amber';
  };

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>Internship Board</h1>
            <p className={styles.subtitle}>Curated ML/AI opportunities · Semantic search powered by pgvector</p>
          </div>
          <span className="badge badge-muted" style={{ fontFamily: 'var(--font-mono)', alignSelf: 'flex-start' }}>
            {filtered.length} listings
          </span>
        </div>

        {/* Search */}
        <div className={styles.searchRow}>
          <div className={styles.searchWrap}>
            <span className={styles.searchIcon}>⌕</span>
            <input
              className={`input ${styles.searchInput}`}
              placeholder="Semantic search: 'PyTorch NLP research', 'Bangalore ML intern'…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={handleSearch}
            disabled={searching || loading}
          >
            {searching ? <><span className="spinner" />Searching…</> : 'Search'}
          </button>
          {searchQuery && (
            <button className="btn btn-ghost" onClick={() => { setSearchQuery(''); fetchAll(); }}>
              Clear
            </button>
          )}
        </div>

        {/* Type filters */}
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

        {error && <div className={styles.error}>{error}</div>}

        {/* Grid */}
        {loading ? (
          <div className={styles.loadingGrid}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={`${styles.skeleton} card`} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}>
            <span style={{ fontSize: 28 }}>◇</span>
            <p>No opportunities found.</p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Try a different search or seed the database via the backend CLI.
            </p>
          </div>
        ) : (
          <div className={styles.grid}>
            {filtered.map(opp => (
              <div key={opp.id} className={`${styles.oppCard} card`}>
                <div className={styles.oppHeader}>
                  <div className={styles.oppMeta}>
                    <span className={styles.oppCompany}>{opp.company}</span>
                    <span className={styles.oppDot}>·</span>
                    <span className={styles.oppLocation}>{opp.location}</span>
                  </div>
                  <div className={styles.oppBadges}>
                    <span className={`badge ${matchColor(opp.match_score)}`}>
                      {opp.match_score != null ? `${Math.round(opp.match_score * 100)}% match` : opp.type}
                    </span>
                  </div>
                </div>

                <h3 className={styles.oppTitle}>{opp.title}</h3>

                {opp.description && (
                  <p className={styles.oppDesc}>{opp.description.slice(0, 180)}{opp.description.length > 180 ? '…' : ''}</p>
                )}

                <div className={styles.oppSkills}>
                  {opp.skills_required.slice(0, 5).map(s => (
                    <span key={s} className="badge badge-muted">{s}</span>
                  ))}
                  {opp.skills_required.length > 5 && (
                    <span className="badge badge-muted">+{opp.skills_required.length - 5}</span>
                  )}
                </div>

                <div className={styles.oppFooter}>
                  <div className={styles.oppMeta2}>
                    {opp.stipend && <span className={styles.stipend}>₹ {opp.stipend}</span>}
                    {opp.deadline && <span className={styles.deadline}>Due {opp.deadline}</span>}
                  </div>
                  {opp.url && (
                    <a
                      href={opp.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-ghost"
                      style={{ padding: '4px 10px', fontSize: 12, textDecoration: 'none' }}
                    >
                      Apply →
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
