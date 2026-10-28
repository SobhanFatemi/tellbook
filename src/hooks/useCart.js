import { useSyncExternalStore } from "react";
const STORAGE = "tellbook_cart_v1";
const empty = { lines: [], key: "" };
let cached;
function read() {
  if (cached) return cached;
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE));
    cached = value && Array.isArray(value.lines) && value.lines.every(l => l && Number.isInteger(l.quantity) && l.quantity > 0 && l.quantity <= 20 && (l.product_id || l.edition_id)) ? value : empty;
  } catch { cached = empty; }
  return cached;
}
const listeners = new Set();
function publish(lines) {
  cached = { lines, key: crypto.randomUUID() };
  try { localStorage.setItem(STORAGE, JSON.stringify(cached)); } catch { /* Keep a working in-memory cart when storage is unavailable. */ }
  listeners.forEach(fn => fn());
}
window.addEventListener("storage", event => { if (event.key === STORAGE) { cached = null; listeners.forEach(fn => fn()); } });
function identity(line) { return line.product_id ? `p${line.product_id}` : `e${line.edition_id}`; }
export function addToCart(line) {
  const lines = read().lines;
  const existing = lines.find(row => identity(row) === identity(line));
  publish(existing ? lines.map(row => identity(row) === identity(line) ? { ...line, quantity: Math.min(20, row.quantity + 1) } : row) : [...lines, { ...line, quantity: 1 }]);
}
export function useCart() {
  const cart = useSyncExternalStore(fn => { listeners.add(fn); return () => listeners.delete(fn); }, read);
  return { ...cart, count: cart.lines.reduce((sum, l) => sum + l.quantity, 0),
    setQuantity: (line, quantity) => publish(cart.lines.map(l => identity(l) === identity(line) ? { ...l, quantity } : l)),
    remove: line => publish(cart.lines.filter(l => identity(l) !== identity(line))),
    clear: () => publish([]) };
}
