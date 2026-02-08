import { useEffect, useRef } from 'react';

interface UseBarcodeScanOptions {
  onScan: (barcode: string) => void;
  minLength?: number;
  maxGapMs?: number;
}

export function useBarcodeScan({ onScan, minLength = 3, maxGapMs = 80 }: UseBarcodeScanOptions) {
  const buffer = useRef('');
  const lastKeyTime = useRef(0);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const tag = target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable) {
        return;
      }

      const now = Date.now();
      if (now - lastKeyTime.current > maxGapMs) {
        buffer.current = '';
      }
      lastKeyTime.current = now;

      if (e.key === 'Enter') {
        if (buffer.current.length >= minLength) {
          onScan(buffer.current);
        }
        buffer.current = '';
        return;
      }

      if (e.key.length === 1) {
        buffer.current += e.key;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onScan, minLength, maxGapMs]);
}
