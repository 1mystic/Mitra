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
        <div className={styles.brandMark}>
          <svg width="15" height="15" viewBox="0 0 22 22" fill="none">
            <polygon
              points="11,1 20.5,6 20.5,16 11,21 1.5,16 1.5,6"
              stroke="#050507" strokeWidth="1.8"
              fill="transparent"
            />
            <polygon
              points="11,5.5 17,9 17,13 11,16.5 5,13 5,9"
              stroke="#050507" strokeWidth="1.2"
              fill="none" strokeOpacity="0.5"
            />
          </svg>
        </div>
        <span className={styles.brandName}>Mitra</span>
        <span className={styles.brandTag}>AI</span>
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
        {authed ? (
          <button onClick={handleLogout} className={styles.signOutBtn}>
            Sign out
          </button>
        ) : (
          <Link href="/auth" className={styles.signInBtn}>
            Sign in
          </Link>
        )}
      </div>
    </nav>
  );
}
