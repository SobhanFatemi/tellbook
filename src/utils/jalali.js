/** ISO date string -> "۱۴ مهر ۱۴۰۳، ۱۰:۳۲" using the Persian calendar. */
export function formatJalali(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  return "\u2067" + new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date) + "\u2069";
}

/** Shorter form for lists: "۱۴ مهر ۱۴۰۳" */
export function formatJalaliShort(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  return "\u2067" + new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date) + "\u2069";
}

/** Whole days remaining until an ISO deadline, floored (can be negative if past). */
export function daysRemaining(isoString) {
  if (!isoString) return null;
  const diffMs = new Date(isoString).getTime() - Date.now();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}
