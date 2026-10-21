import React from 'react';
export const number = value => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 });

export function Download({ rows, filename, children }) {
  return <button disabled={!rows.length} onClick={() => {
    const url = URL.createObjectURL(new Blob([toCSV(rows)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }}>{children}</button>;
}

export function Table({ rows, fields, caption }) {
  return <div className="table-wrap"><table><caption>{caption}</caption><thead><tr>{fields.map(([key, title]) => <th key={key} scope="col">{title}</th>)}</tr></thead>
    <tbody>{rows.map((row, i) => <tr key={i}>{fields.map(([key]) => <td key={key}>{typeof row[key] === 'number' ? number(row[key]) : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table></div>;
}

export function Chart({ rows, series, title, percent = false }) {
  const values = rows.flatMap(row => series.map(s => row[s.key]).filter(v => v != null && Number.isFinite(v)));
  if (!values.length) return <section><h3>{title}</h3><p>No valid values in this range. Edge momentum observations remain gaps.</p></section>;
  const width = 960, height = 235, left = 70, right = 20, top = 15, bottom = 35;
  let min = percent ? 0 : Math.min(0, ...values), max = percent ? 100 : Math.max(...values);
  if (max === min) max = min + 1;
  const x = i => left + i / Math.max(rows.length - 1, 1) * (width - left - right);
  const y = v => top + (max - v) / (max - min) * (height - top - bottom);
  return <section><h3>{title}</h3><div className="legend">{series.map(s => <span key={s.key} style={{ color: s.color }}>● {s.label}</span>)}</div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}. ${rows[0].date} through ${rows.at(-1).date}.`}>
      {[min, (min + max) / 2, max].map(tick => <g key={tick}><line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} stroke="#ddd"/><text x={left - 10} y={y(tick) + 4} textAnchor="end">{number(tick)}</text></g>)}
      <text x={left} y={height - 8}>{rows[0].date}</text><text x={width - right} y={height - 8} textAnchor="end">{rows.at(-1).date}</text>
      {series.map(s => {
        let path = '', gap = true;
        rows.forEach((row, i) => { const value = row[s.key]; if (value == null || !Number.isFinite(value)) { gap = true; return; } path += `${gap ? 'M' : 'L'}${x(i)},${y(value)} `; gap = false; });
        return <g key={s.key}><path d={path} stroke={s.color} fill="none" strokeWidth="1.7"/>{rows.map((row, i) => row[s.key] == null ? null : <circle key={i} cx={x(i)} cy={y(row[s.key])} r={4} fill={s.color} opacity={rows.length === 1 ? 1 : 0}><title>{row.date} · {s.label}: {number(row[s.key])}</title></circle>)}</g>;
      })}
    </svg></section>;
}

