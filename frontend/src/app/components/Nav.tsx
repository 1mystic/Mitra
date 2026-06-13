'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Nav.module.css';

const NAV_LINKS = [
  { href: '/',              label: 'Home',       icon: '◈' },
  { href: '/chat',          label: 'Chat',        icon: '⌬' },
  { href: '/profile',       label: 'Profile',     icon: '◎' },
  { href: '/opportunities', label: 'Internships', icon: '◇' },
  { href: '/tracker',       label: 'Tracker',     icon: '▦' },
];

export default function Nav() {
  const path = usePathname();

  return (
    <nav className={styles.nav}>
      <div className={styles.brand}>
        <span className={styles.brandIcon}>⬡</span>
        <span className={styles.brandName}>mitra</span>
        <span className={styles.brandVersion}>v2.0</span>
      </div>

      <div className={styles.links}>
        {NAV_LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`${styles.link} ${path === l.href ? styles.active : ''}`}
          >
            <span className={styles.linkIcon}>{l.icon}</span>
            <span className={styles.linkLabel}>{l.label}</span>
          </Link>
        ))}
      </div>

      <div className={styles.status}>
        <span className={styles.dot} />
        <span className={styles.statusText}>AI Online</span>
      </div>
    </nav>
  );
}
