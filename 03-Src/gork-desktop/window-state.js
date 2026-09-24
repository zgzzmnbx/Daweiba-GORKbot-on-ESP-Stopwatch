function visibleBounds(saved, displays) {
  if (!saved || !Number.isFinite(saved.x) || !Number.isFinite(saved.y)) return null;
  const width = Math.min(360, Math.max(60, Number.isFinite(saved.width) ? saved.width : 240));
  const height = Math.min(420, Math.max(70, Number.isFinite(saved.height) ? saved.height : 280));
  const visible = displays.some(({ workArea }) => {
    const overlapX = Math.min(saved.x + width, workArea.x + workArea.width) - Math.max(saved.x, workArea.x);
    const overlapY = Math.min(saved.y + height, workArea.y + workArea.height) - Math.max(saved.y, workArea.y);
    return overlapX >= Math.min(80, width) && overlapY >= Math.min(80, height);
  });
  return visible ? { x: saved.x, y: saved.y, width, height } : null;
}

function avatarBoundsForScale(bounds, percent, workArea) {
  if (!Number.isInteger(percent) || percent < 25 || percent > 150) throw new Error('Avatar size must be 25–150 percent');
  const width = Math.round(240 * percent / 100), height = Math.round(280 * percent / 100);
  const x = Math.max(workArea.x, Math.min(bounds.x, workArea.x + workArea.width - width));
  const y = Math.max(workArea.y, Math.min(bounds.y, workArea.y + workArea.height - height));
  return {x, y, width, height};
}
module.exports = { visibleBounds, avatarBoundsForScale };
