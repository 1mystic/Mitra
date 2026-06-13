'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { isAuthenticated, removeToken } from '@/lib/auth';
import styles from './Nav.module.css';

const LINKS = [
  { href: '/chat',          label: 'Chat' },
  { href: '/profile',       label: 'Profile' },
  { href: '/opportunities', label: 'Internships' },
  { href: '/tracker',       label: 'Tracker' },
];

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const isLanding = path === '/';
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, [path]);

  function handleLogout() {
    removeToken();
    router.push('/auth');
  }

  return (
    <nav className={`${styles.nav} ${isLanding ? styles.navTransparent : styles.navSolid}`}>
      <Link href="/" className={styles.brand}>
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <polygon
            points="11,1 20.5,6 20.5,16 11,21 1.5,16 1.5,6"
            stroke="currentColor" strokeWidth="1.5"
            fill="rgba(255,255,255,0.06)"
          />
          <polygon
            points="11,5.5 17,9 17,13 11,16.5 5,13 5,9"
            stroke="currentColor" strokeWidth="1"
            fill="none" strokeOpacity="0.4"
          />
        </svg>
        <span className={styles.brandName}>Mitra</span>
      </Link>

      <div className={styles.links}>
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`${styles.link} ${path === l.href ? styles.active : ''}`}
          >
            {l.label}
          </Link>
        ))}
      </div>

      <div className={styles.right}>
        <span className={styles.statusDot} aria-hidden />
        <span className={styles.statusLabel}>AI Online</span>
        {authed && (
          <button
            onClick={handleLogout}
            style={{
              marginLeft: '12px',
              background: 'none',
              border: '1px solid var(--line-strong)',
              borderRadius: 'var(--r-pill)',
              color: 'var(--text-2)',
              fontSize: '12px',
              padding: '4px 12px',
              cursor: 'pointer',
            }}
          >
            Sign out
          </button>
        )}
      </div>
    </nav>
  );
}
