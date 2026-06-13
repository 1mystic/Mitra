'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated, getUserId } from './auth';

/**
 * Redirect to /auth if no token is present.
 * Returns the stored user_id (or null while not yet checked).
 */
export function useRequireAuth(): string | null {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/auth');
    }
  }, [router]);

  return getUserId();
}
