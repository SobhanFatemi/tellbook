import { useState } from "react";
import { Input } from "./FormFields";
import { formatToman, parseGroupedNumber } from "../utils/persianFormat";

export default function PriceRangeFilter({ bounds, minimum, maximum, onCommit }) {
  const floor = bounds?.min_price;
  const ceiling = bounds?.max_price;
  const available = Number.isFinite(floor) && Number.isFinite(ceiling);
  const clamp = (value, low, high) => Math.min(high, Math.max(low, Number(value)));
  const initialLow = available ? clamp(minimum === "" ? floor : minimum, floor, ceiling) : 0;
  const initialHigh = available ? clamp(maximum === "" ? ceiling : maximum, initialLow, ceiling) : 0;
  const [low, setLow] = useState(initialLow);
  const [high, setHigh] = useState(initialHigh);
  const [lowText, setLowText] = useState(String(initialLow));
  const [highText, setHighText] = useState(String(initialHigh));

  const [committedRange, setCommittedRange] = useState(null);
  const rangeKey = `${initialLow}:${initialHigh}`;
  const [previousRange, setPreviousRange] = useState(rangeKey);
  // Sync URL/back-button changes before rendering without remounting focused controls.
  if (previousRange !== rangeKey) {
    setPreviousRange(rangeKey);
    if (committedRange !== rangeKey) {
      setLow(initialLow); setHigh(initialHigh);
      setLowText(String(initialLow)); setHighText(String(initialHigh));
    }
  }

  function commit(nextLow, nextHigh) {
    setCommittedRange(`${nextLow}:${nextHigh}`);
    onCommit(nextLow, nextHigh);
  }

  function commitText(which, rawValue) {
    const text = parseGroupedNumber(rawValue);
    const previous = which === "min" ? low : high;
    const value = text.trim() !== "" && Number.isFinite(Number(text)) ? Math.round(Number(text)) : previous;
    const nextLow = which === "min" ? clamp(value, floor, high) : low;
    const nextHigh = which === "max" ? clamp(value, low, ceiling) : high;
    setLow(nextLow); setHigh(nextHigh);
    setLowText(String(nextLow)); setHighText(String(nextHigh));
    commit(nextLow, nextHigh);
  }

  const percent = value => ceiling === floor ? 50 : (value - floor) / (ceiling - floor) * 100;
  function change(item, raw) {
    const value = clamp(Math.round(raw), item.min, item.max);
    (item.key === "min" ? setLow : setHigh)(value);
    (item.key === "min" ? setLowText : setHighText)(String(value));
    return value;
  }
  function movePointer(event, item) {
    const rect = event.currentTarget.parentElement.getBoundingClientRect();
    return change(item, floor + (rect.right - event.clientX) / rect.width * (ceiling - floor));
  }

  return <fieldset className="price-range-filter">
    <legend className="field-label">بازه قیمت (تومان)</legend>
    {!available ? <p className="text-sm text-ink-400">{bounds ? "هنوز قیمت قابل انتخابی ثبت نشده است." : "در حال دریافت بازه قیمت…"}</p> : <>
      <p className="price-range-caption">از {formatToman(floor)} تا {formatToman(ceiling)}</p>
      <div className="price-range-track" role="group" aria-label="انتخاب بازه قیمت">
        <div className="price-range-rail" />
        <div className="price-range-selection" style={{ right: `${percent(low)}%`, left: `${100 - percent(high)}%` }} />
        {[{ key: "min", label: "حداقل قیمت", value: low, min: floor, max: high }, { key: "max", label: "حداکثر قیمت", value: high, min: low, max: ceiling }].map(item =>
          <button key={item.key} type="button" role="slider" className="price-range-handle"
            aria-label={`${item.label} با کشیدن`} aria-valuemin={item.min} aria-valuemax={item.max} aria-valuenow={item.value} aria-valuetext={formatToman(item.value)}
            disabled={floor === ceiling} style={{ right: `${percent(item.value)}%`, zIndex: item.key === "min" && low === ceiling ? 3 : 2 }}
            onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.focus(); }}
            onPointerMove={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) movePointer(e, item); }}
            onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) { const value = movePointer(e, item); e.currentTarget.releasePointerCapture(e.pointerId); commit(item.key === "min" ? value : low, item.key === "max" ? value : high); } }}
            onPointerCancel={() => commit(low, high)}
            onKeyDown={e => {
              const step = Math.max(1, Math.round((ceiling - floor) / 100));
              const changes = { ArrowLeft: step, ArrowUp: step, ArrowRight: -step, ArrowDown: -step, PageUp: step * 10, PageDown: -step * 10 };
              if (!(e.key in changes) && e.key !== "Home" && e.key !== "End") return;
              e.preventDefault();
              const value = change(item, e.key === "Home" ? item.min : e.key === "End" ? item.max : item.value + changes[e.key]);
              commit(item.key === "min" ? value : low, item.key === "max" ? value : high);
            }} />)}
      </div>
      <div className="price-range-controls">
        {[{ key: "min", label: "حداقل قیمت", value: low, text: lowText, min: floor, max: high }, { key: "max", label: "حداکثر قیمت", value: high, text: highText, min: low, max: ceiling }].map(item => <div key={item.key}>
          <Input groupDigits label={item.label} type="number" value={item.text} min={item.min} max={item.max}
            onChange={e => (item.key === "min" ? setLowText : setHighText)(e.target.value)}
            onBlur={e => commitText(item.key, e.currentTarget.value)}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); commitText(item.key, e.currentTarget.value); } }} />
        </div>)}
      </div>
    </>}
  </fieldset>;
}
