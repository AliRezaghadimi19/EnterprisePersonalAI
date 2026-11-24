/**
 * Shared hooks — list fetching with reload, debounced values, form state.
 */
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { PagedResult } from './api';
import { normalizeList } from './api';

/** Fetch-and-hold list pattern used by every admin list page. */
export function useApiList<T>(
  fetcher: () => Promise<unknown>,
  deps: unknown[] = [],
  wrapperKeys?: string[]
): {
  data: PagedResult<T> | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [data, setData] = useState<PagedResult<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const wrapperRef = useRef(wrapperKeys);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await fetcherRef.current();
      // api.* helpers already normalize to {items,total}; 'items' key makes
      // normalizeList a no-op for pre-normalized results (avoids double unwrap).
      setData(normalizeList<T>(raw, ['items', ...(wrapperRef.current || [])]));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطای ناشناخته');
      setData({ items: [], total: 0 });
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload };
}

/** Debounce a changing value (search inputs). */
export function useDebounce<T>(value: T, delayMs = 400): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export interface FormStateApi<T> {
  values: T;
  setField: (name: keyof T, value: unknown) => void;
  setValues: (v: T) => void;
  errors: Partial<Record<keyof T, string>>;
  setErrors: (errors: Partial<Record<keyof T, string>>) => void;
  reset: (initial?: T) => void;
  submitting: boolean;
  setSubmitting: (v: boolean) => void;
}

/** Minimal form-state helper for modal forms — no form library. */
export function useFormState<T extends Record<string, unknown>>(initial: T): FormStateApi<T> {
  const [values, setValuesState] = useState<T>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const initialRef = useRef(initial);

  const setField = useCallback((name: keyof T, value: unknown) => {
    setValuesState((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const setValues = useCallback((v: T) => setValuesState(v), []);

  const reset = useCallback((init?: T) => {
    setValuesState(init ?? (initialRef.current as T));
    setErrors({});
  }, []);

  return { values, setField, setValues, errors, setErrors, reset, submitting, setSubmitting };
}