import Link from 'next/link';
import styles from './Footer.module.css';

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        {/* Brand */}
        <div className={styles.brand}>
          <div className={styles.brandMark} aria-hidden>
            <svg width="13" height="13" viewBox="0 0 22 22" fill="none">
              <polygon points="11,1 20.5,6 20.5,16 11,21 1.5,16 1.5,6"
                stroke="#050507" strokeWidth="1.8" fill="transparent" />
            </svg>
          </div>
          <span className={styles.brandName}>Mitra</span>
          <span className={styles.brandDesc}>AI career intelligence for ML/AI students</span>
        </div>

        {/* Account links */}
        <div className={styles.linkGroup}>
          <span className={styles.groupLabel}>Account</span>
          <Link href="/auth" className={styles.link}>Sign in</Link>
          <Link href="/auth?tab=register" className={styles.link}>Create account</Link>
          <Link href="/onboarding" className={styles.link}>Upload resume</Link>
        </div>

        {/* Project links */}
        <div className={styles.linkGroup}>
          <span className={styles.groupLabel}>Project</span>
          <Link href="/about" className={styles.link}>About</Link>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className={styles.link}>GitHub</a>
        </div>
      </div>

      <div className={styles.bottom}>
        <span className={styles.copy}>© {new Date().getFullYear()} Mitra</span>
        <span className={styles.stack}>FastAPI · LangGraph · pgvector · Claude 4</span>
      </div>
    </footer>
  );
}
