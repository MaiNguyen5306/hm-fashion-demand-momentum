import React, { useId, useState } from 'react';
import { nearestChartIndex, moveChartIndex } from './chart-interaction.js';
import { toCSV } from './data.js';
export const number = value => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });

export function Download({ rows, filename, children }) {
  return <button className="download-data-link" disabled={!rows.length} onClick={() => {
    const url = URL.createObjectURL(new Blob([toCSV(rows)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}>{children}</button>;
}

export function Table({ rows, fields, caption }) {
  return <div className="table-wrap"><table><caption>{caption}</caption><thead><tr>{fields.map(([key, title]) => <th key={key} scope="col">{title}</th>)}</tr></thead>
    <tbody>{rows.map((row, i) => <tr key={i}>{fields.map(([key]) => <td key={key}>{typeof row[key] === 'number' ? number(row[key]) : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table></div>;
}

const chartDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value.slice(5,7)}/${value.slice(8,10)}/${value.slice(2,4)}` : value;

export function Chart({ rows, series, title, percent = false, interactive = false, tooltipFields }) {
  const [activeIndex, setActiveIndex] = useState(null);
  const hintId = useId();
  const values = rows.flatMap(row => series.map(s => row[s.key]).filter(v => v != null && Number.isFinite(v)));
  if (!values.length) return <section><h3>{title}</h3><p>No valid values in this range. Edge momentum observations remain gaps.</p></section>;
  const width = 960, height = 235, left = 70, right = 20, top = 15, bottom = 35;
  let min = percent ? 0 : Math.min(0, ...values), max = percent ? 100 : Math.max(...values);
  if (max === min) max = min + 1;
  const x = i => left + i / Math.max(rows.length - 1, 1) * (width - left - right);
  const y = v => top + (max - v) / (max - min) * (height - top - bottom);
  const index = activeIndex == null ? null : Math.min(activeIndex, rows.length - 1);
  const active = index == null ? null : rows[index];
  const fields = tooltipFields || series.map(s => ({key:s.key,label:s.label,suffix:percent ? '%' : ''}));
  const describe = row => `${chartDate(row.date)}. ${fields.map(f => `${f.label}: ${number(row[f.key])}${f.suffix || ''}`).join('. ')}`;
  const inspectPointer = event => {
    const bounds = event.currentTarget.getBoundingClientRect();
    setActiveIndex(nearestChartIndex(event.clientX, bounds.left, bounds.width, rows.length));
  };
  return <section><h3>{title}</h3><div className="legend">{series.map(s => <span key={s.key} style={{ color: s.color }}>● {s.label}</span>)}</div>
    {interactive && <p id={hintId} className="chart-interaction-hint">Hover or drag to inspect a date. Focus the chart and use ← / →; Home / End jump to the first / last date.</p>}
    <div className={interactive ? 'interactive-chart' : undefined} tabIndex={interactive ? 0 : undefined} role={interactive ? 'group' : undefined} aria-label={interactive ? `${title}: interactive chart` : undefined} aria-describedby={interactive ? hintId : undefined}
      onFocus={interactive ? () => setActiveIndex(value => value ?? 0) : undefined}
      onBlur={interactive ? () => setActiveIndex(null) : undefined}
      onKeyDown={interactive ? event => { if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) { event.preventDefault(); setActiveIndex(value => moveChartIndex(value,event.key,rows.length)); } else if(event.key === 'Escape') setActiveIndex(null); } : undefined}>
    <svg onPointerMove={interactive ? inspectPointer : undefined} onPointerDown={interactive ? event => { event.currentTarget.setPointerCapture(event.pointerId); inspectPointer(event); } : undefined} onPointerLeave={interactive ? event => { if(event.pointerType === 'mouse') setActiveIndex(null); } : undefined} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. ${chartDate(rows[0].date)} through ${chartDate(rows.at(-1).date)}.`}>
      {[min, (min + max) / 2, max].map(tick => <g key={tick}><line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} stroke="#ddd"/><text x={left - 10} y={y(tick) + 4} textAnchor="end">{number(tick)}</text></g>)}
      <text x={left} y={height - 8}>{chartDate(rows[0].date)}</text><text x={width - right} y={height - 8} textAnchor="end">{chartDate(rows.at(-1).date)}</text>
      {series.map(s => {
        let path = '', gap = true;
        rows.forEach((row, i) => { const value = row[s.key]; if (value == null || !Number.isFinite(value)) { gap = true; return; } path += `${gap ? 'M' : 'L'}${x(i)},${y(value)} `; gap = false; });
        return <g key={s.key}><path d={path} stroke={s.color} fill="none" strokeWidth="1.7"/>{rows.map((row, i) => row[s.key] == null ? null : <circle key={i} cx={x(i)} cy={y(row[s.key])} r={4} fill={s.color} opacity={rows.length === 1 ? 1 : 0}><title>{chartDate(row.date)} · {s.label}: {number(row[s.key])}</title></circle>)}</g>;
      })}
      {interactive && active && <g pointerEvents="none"><line x1={x(index)} x2={x(index)} y1={top} y2={height-bottom} stroke="#aa8190" strokeDasharray="4 4"/>{series.map(s => Number.isFinite(active[s.key]) ? <circle key={s.key} cx={x(index)} cy={y(active[s.key])} r="4" fill={s.color} stroke="#fff" strokeWidth="1.5"/> : null)}</g>}
    </svg>
    {interactive && active && <div className="chart-value-tooltip" role="tooltip" style={index < rows.length/2 ? {left:`${Math.min(65,x(index)/width*100)}%`} : {right:`${Math.min(65,(width-x(index))/width*100)}%`}}><strong>{chartDate(active.date)}</strong>{fields.map(f => <span key={f.key}>{f.label}<b>{number(active[f.key])}{f.suffix || ''}</b></span>)}</div>}
    {interactive && <span className="chart-screen-reader" aria-live="polite" aria-atomic="true">{active ? describe(active) : ''}</span>}
    </div></section>;
}

