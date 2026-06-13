import type { Metadata } from 'next';
import Nav from './components/Nav';
import './globals.css';

export const metadata: Metadata = {
  title: 'Mitra — Career Intelligence OS',
  description: 'Multi-agent AI career companion for ML/AI students in India',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <Nav />
        <div style={{ paddingTop: 'var(--nav-h)' }}>
          {children}
        </div>
      </body>
    </html>
  );
}
