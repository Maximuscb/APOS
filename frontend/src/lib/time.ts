// frontend/src/lib/time.ts

// Convert an <input type="datetime-local"> value (local time, no tz) into UTC ISO with 'Z'.
// Returns null if blank or invalid.
export function datetimeLocalToUtcIso(value: string): string | null {
  const v = value.trim();
  if (!v) return null;

  // datetime-local is like "YYYY-MM-DDTHH:mm" (sometimes with seconds).
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;

  return d.toISOString(); // UTC with trailing 'Z'
}

// For display only: UTC ISO -> user’s local time string.
export function utcIsoToLocalDisplay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
