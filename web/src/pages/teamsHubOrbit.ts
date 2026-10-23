export type OrbitNodeSize = { width: number; height: number };

// Reserve the largest hover/focus scale for every card, including empty ones.
// The same gap applies to neighbouring cards and the stage's outside edge.
const SCALE = 1.08;
const GAP = 16;

export function orbitLayout(width: number, height: number, nodes: OrbitNodeSize[]) {
  const angles = nodes.map((_, index) => -Math.PI / 2 + index * 2 * Math.PI / nodes.length);
  const maxWidth = Math.max(...nodes.map((node) => node.width * SCALE));
  const maxHeight = Math.max(...nodes.map((node) => node.height * SCALE));
  const rx = Math.min(520, Math.max(0, (width - maxWidth) / 2 - GAP));
  let minRy = 0;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = Math.abs(Math.cos(angles[i]) - Math.cos(angles[j])) * rx;
      const dy = Math.abs(Math.sin(angles[i]) - Math.sin(angles[j]));
      // If X cannot separate the scaled rectangles, Y must. The symmetric
      // bottom pair shares a Y coordinate and is already separated on desktop.
      if (dx < (nodes[i].width + nodes[j].width) * SCALE / 2 + GAP && dy > 1e-6) {
        minRy = Math.max(minRy, ((nodes[i].height + nodes[j].height) * SCALE / 2 + GAP) / dy);
      }
    }
  }
  const minHeight = Math.ceil(minRy * 2 + maxHeight + GAP * 2);
  const ry = Math.max(minRy, (height - maxHeight) / 2 - GAP);
  return {
    minHeight,
    points: angles.map((angle) => ({ x: width / 2 + rx * Math.cos(angle), y: height / 2 + ry * Math.sin(angle) })),
  };
}
