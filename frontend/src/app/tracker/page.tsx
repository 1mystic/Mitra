'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { tracker } from '@/lib/api';
import type { Application, AppStatus } from '@/lib/types';
import styles from './page.module.css';

const COLUMNS: { status: AppStatus; label: string; color: string }[] = [
  { status: 'wishlist',    label: 'Wishlist',     color: 'var(--text-muted)' },
  { status: 'applied',     label: 'Applied',      color: 'var(--blue)' },
  { status: 'interviewing',label: 'Interviewing', color: 'var(--amber)' },
  { status: 'offer',       label: 'Offer',        color: 'var(--teal)' },
  { status: 'rejected',    label: 'Rejected',     color: 'var(--red)' },
];

const STATUS_BADGE: Record<AppStatus, string> = {
  wishlist:     'badge-muted',
  applied:      'badge-blue',
  interviewing: 'badge-amber',
  offer:        'badge-teal',
  rejected:     'badge-red',
};

export default function TrackerPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ company: '', role: '', status: 'wishlist' as AppStatus, notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const id = localStorage.getItem('mitra_user_id');
    if (!id) { router.push('/'); return; }
    setUserId(id);
    tracker.list(id)
      .then(setApps)
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!userId || !form.company.trim() || !form.role.trim()) return;
    setSaving(true);
    try {
      const app = await tracker.create({
        user_id: userId,
        company: form.company,
        role: form.role,
        status: form.status,
        notes: form.notes || undefined,
      });
      setApps(prev => [app, ...prev]);
      setForm({ company: '', role: '', status: 'wishlist', notes: '' });
      setAddOpen(false);
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleMove(appId: string, status: AppStatus) {
    try {
      const updated = await tracker.update(appId, { status });
      setApps(prev => prev.map(a => a.id === appId ? updated : a));
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleDelete(appId: string) {
    try {
      await tracker.delete(appId);
      setApps(prev => prev.filter(a => a.id !== appId));
    } catch (err) {
      setError(String(err));
    }
  }

  const byStatus = (status: AppStatus) => apps.filter(a => a.status === status);

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <div>
          <h1 className={styles.title}>Application Tracker</h1>
          <p className={styles.subtitle}>Drag-free kanban · {apps.length} applications tracked</p>
        </div>
        <button className="btn btn-primary" onClick={() => setAddOpen(true)}>
          + Add Application
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {/* Add modal */}
      {addOpen && (
        <div className={styles.modalOverlay} onClick={e => e.target === e.currentTarget && setAddOpen(false)}>
          <div className={`${styles.modal} card`}>
            <div className={styles.modalHeader}>
              <span className={styles.modalTitle}>Add Application</span>
              <button onClick={() => setAddOpen(false)} style={{ color: 'var(--text-muted)', fontSize: 18 }}>×</button>
            </div>
            <form onSubmit={handleAdd} className={styles.addForm}>
              <div className={styles.formRow}>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Company *</label>
                  <input className="input" value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} placeholder="Google, DeepMind…" required />
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Role *</label>
                  <input className="input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} placeholder="ML Research Intern" required />
                </div>
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Status</label>
                <select className="input" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value as AppStatus }))}>
                  {COLUMNS.map(c => <option key={c.status} value={c.status}>{c.label}</option>)}
                </select>
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Notes</label>
                <textarea className="input" rows={3} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Referral? Deadline? Key contacts…" style={{ resize: 'vertical' }} />
              </div>
              <div className={styles.formActions}>
                <button type="button" className="btn btn-ghost" onClick={() => setAddOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? <><span className="spinner" />Saving…</> : 'Add Application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className={styles.loadingBar}><span className="spinner" /><span>Loading applications…</span></div>
      ) : (
        <div className={styles.kanban}>
          {COLUMNS.map(col => {
            const colApps = byStatus(col.status);
            return (
              <div key={col.status} className={styles.column}>
                <div className={styles.colHeader}>
                  <span className={styles.colDot} style={{ background: col.color }} />
                  <span className={styles.colLabel}>{col.label}</span>
                  <span className={styles.colCount}>{colApps.length}</span>
                </div>

                <div className={styles.cards}>
                  {colApps.length === 0 ? (
                    <div className={styles.emptyCol}>—</div>
                  ) : (
                    colApps.map(app => (
                      <AppCard
                        key={app.id}
                        app={app}
                        onMove={handleMove}
                        onDelete={handleDelete}
                        columns={COLUMNS}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AppCard({
  app,
  onMove,
  onDelete,
  columns,
}: {
  app: Application;
  onMove: (id: string, s: AppStatus) => void;
  onDelete: (id: string) => void;
  columns: typeof COLUMNS;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className={styles.appCard}>
      <div className={styles.appCardTop}>
        <div>
          <div className={styles.appCompany}>{app.company}</div>
          <div className={styles.appRole}>{app.role}</div>
        </div>
        <div className={styles.appActions}>
          <button
            className={styles.menuTrigger}
            onClick={() => setMenuOpen(o => !o)}
            title="Move / delete"
          >
            ⋯
          </button>
          {menuOpen && (
            <div className={styles.menu}>
              <span className={styles.menuLabel}>Move to</span>
              {columns.filter(c => c.status !== app.status).map(c => (
                <button
                  key={c.status}
                  className={styles.menuItem}
                  onClick={() => { onMove(app.id, c.status); setMenuOpen(false); }}
                >
                  {c.label}
                </button>
              ))}
              <div className={styles.menuDivider} />
              <button
                className={`${styles.menuItem} ${styles.menuDelete}`}
                onClick={() => { onDelete(app.id); setMenuOpen(false); }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {app.notes && <p className={styles.appNotes}>{app.notes}</p>}

      <div className={styles.appFooter}>
        <span className={`badge ${STATUS_BADGE[app.status]}`}>{app.status}</span>
        {app.applied_at && (
          <span className={styles.appDate}>
            {new Date(app.applied_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  );
}
