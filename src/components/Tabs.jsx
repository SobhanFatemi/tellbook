export default function Tabs({ tabs, active, onChange }) {
  return <div className="status-tabs" role="group" aria-label="فیلتر وضعیت">{tabs.map(tab => <button type="button" key={tab.value} className="status-tab" aria-pressed={active === tab.value} onClick={() => onChange(tab.value)}>{tab.label}</button>)}</div>;
}
