/** Shared treatment for staff review actions, including payment receipts. */
export default function AdminActionPanel({ title, summary, children }) {
  return <section className="payment-review" aria-label={title}>
    <div className="payment-review-heading"><h3>{title}</h3>{summary != null && <span>{summary}</span>}</div>
    {children}
  </section>;
}
