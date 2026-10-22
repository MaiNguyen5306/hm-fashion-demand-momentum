export function nearestChartIndex(clientX, boundsLeft, boundsWidth, count) {
  if (count <= 1 || boundsWidth <= 0) return 0;
  const svgX = (clientX - boundsLeft) / boundsWidth * 960;
  return Math.max(0, Math.min(count - 1, Math.round((svgX - 70) / 870 * (count - 1))));
}
export function moveChartIndex(current, key, count) {
  const index = current ?? 0;
  if (key === 'Home') return 0;
  if (key === 'End') return Math.max(0, count - 1);
  return Math.max(0, Math.min(count - 1, index + (key === 'ArrowRight' ? 1 : key === 'ArrowLeft' ? -1 : 0)));
}
