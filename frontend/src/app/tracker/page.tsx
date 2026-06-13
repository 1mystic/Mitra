'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { tracker } from '@/lib/api';
import { getUserId } from '@/lib/auth';
import type { Application, AppStatus } from '@/lib/types';
import styles from './page.module.css';

const COLUMNS: { status: AppStatus; label: string; dotColor: string }[] = [
  { status: 'wishlist',     label: 'Wishlist',      dotColor: '#555' },
  { status: 'applied',      label: 'Applied',       dotColor: '#4f8ef7' },
  { status: 'interviewing', label: 'Interviewing',  dotColor: '#f59e0b' },
  { status: 'offer',        label: 'Offer',         dotColor: '#3fb950' },
  { status: 'rejected',     label: 'Rejected',      dotColor: '#ef4444' },
];

const STATUS_CLS: Record<AppStatus, string> = {
  wishlist:     styles.statusWishlist,
  applied:      styles.statusApplied,
  interviewing: styles.statusInterviewing,
  offer:        styles.statusOffer,
  rejected:     styles.statusRejected,
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
    const id = getUserId();
    if (!id) { router.replace('/auth'); return; }
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

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <div>
          <h1 className={styles.title}>Application Tracker</h1>
          <p className={styles.subtitle}>{apps.length} application{apps.length !== 1 ? 's' : ''} tracked</p>
        </div>
        <button className="btn btn-white" onClick={() => setAddOpen(true)}>
          + Add Application
        </button>
      </div>

      {error && <div className={styles.errMsg}>{error}</div>}

      {/* Add modal */}
      {addOpen && (
        <div
          className={styles.modalOverlay}
          onClick={e => { if (e.target === e.currentTarget) setAddOpen(false); }}
        >
          <div className={`${styles.modal} card`}>
            <div className={styles.modalHead}>
              <span className={styles.modalTitle}>Add Application</span>
              <button className={styles.closeBtn} onClick={() => setAddOpen(false)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <form onSubmit={handleAdd} className={styles.addForm}>
              <div className={styles.formRow}>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Company</label>
                  <input
                    className="field-input"
                    placeholder="Google, DeepMind..."
                    value={form.company}
                    onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                    required
                    autoFocus
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Role</label>
                  <input
                    className="field-input"
                    placeholder="ML Research Intern"
                    value={form.role}
                    onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                    required
                  />
                </div>
              </div>

              <div className={styles.field}>
                <label className={styles.fieldLabel}>Status</label>
                <select
                  className="field-input"
                  value={form.status}
                  onChange={e => setForm(f => ({ ...f, status: e.target.value as AppStatus }))}
                >
                  {COLUMNS.map(c => <option key={c.status} value={c.status}>{c.label}</option>)}
                </select>
              </div>

              <div className={styles.field}>
                <label className={styles.fieldLabel}>Notes</label>
                <textarea
                  className="field-input"
                  rows={3}
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Referral contact, deadline, OA link..."
                  style={{ resize: 'vertical' }}
                />
              </div>

              <div className={styles.formActions}>
                <button type="button" className="btn btn-ghost" onClick={() => setAddOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-white" disabled={saving}>
                  {saving
                    ? <><span className="spinner spinner-sm" style={{ borderTopColor: '#000', borderColor: 'rgba(0,0,0,0.15)' }} />Saving</>
                    : 'Add Application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className={styles.loadingRow}>
          <span className="spinner" />
          Loading applications...
        </div>
      ) : (
        <div className={styles.kanban}>
          {COLUMNS.map(col => {
            const colApps = apps.filter(a => a.status === col.status);
            return (
              <div key={col.status} className={styles.column} style={{ '--col-accent': col.dotColor } as React.CSSProperties}>
                <div className={styles.colHead}>
                  <span className={styles.colDot} style={{ background: col.dotColor }} />
                  <span className={styles.colLabel}>{col.label}</span>
                  <span className={styles.colCount}>{colApps.length}</span>
                </div>

                {colApps.length === 0 ? (
                  <div className={styles.emptyCol}>—</div>
                ) : (
                  colApps.map(app => (
                    <AppCard
                      key={app.id}
                      app={app}
                      columns={COLUMNS}
                      onMove={handleMove}
                      onDelete={handleDelete}
                    />
                  ))
                )}
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
  columns,
  onMove,
  onDelete,
}: {
  app: Application;
  columns: typeof COLUMNS;
  onMove: (id: string, s: AppStatus) => void;
  onDelete: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.appCard}>
      <div className={styles.appTop}>
        <div>
          <div className={styles.appCompany}>{app.company}</div>
          <div className={styles.appRole}>{app.role}</div>
        </div>
        <div className={styles.appActions}>
          <button className={styles.menuBtn} onClick={() => setOpen(o => !o)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>
            </svg>
          </button>
          {open && (
            <div className={styles.menu}>
              <span className={styles.menuSub}>Move to</span>
              {columns.filter(c => c.status !== app.status).map(c => (
                <button
                  key={c.status}
                  className={styles.menuItem}
                  onClick={() => { onMove(app.id, c.status); setOpen(false); }}
                >
                  {c.label}
                </button>
              ))}
              <div className={styles.menuLine} />
              <button
                className={`${styles.menuItem} ${styles.menuDelete}`}
                onClick={() => { onDelete(app.id); setOpen(false); }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {app.notes && <p className={styles.appNotes}>{app.notes}</p>}

      <div className={styles.appFoot}>
        <span className={`badge ${STATUS_CLS[app.status]}`}>{app.status}</span>
        {app.applied_at && (
          <span className={styles.appDate}>
            {new Date(app.applied_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
          </span>
        )}
      </div>
    </div>
  );
}
