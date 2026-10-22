import type { Lineup } from "./types";

export async function copyText(text: string, fallback: HTMLElement | null): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Permission denied or an insecure context: try the legacy path.
  }

  let area: HTMLTextAreaElement | null = null;
  try {
    area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    const copied = document.execCommand("copy");
    if (copied) return true;
  } catch {
    // Fall through to selecting the visible command for manual copying.
  } finally {
    area?.remove();
  }

  if (fallback) {
    const selection = window.getSelection();
    if (selection) {
      const range = document.createRange();
      range.selectNodeContents(fallback);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
  return false;
}


export function practicePosition(lineup: Lineup): string | null {
  const { x, y, z, pitch, yaw } = lineup.throw;
  return [x, y, z, pitch, yaw].every(Number.isFinite) ? `setpos ${x} ${y} ${z};setang ${pitch} ${yaw} 0` : null;
}
export function practiceBind(lineup: Lineup): string | null {
  const command = practicePosition(lineup);
  return command ? `bind "KP_ENTER" "${command}"` : null;
}
export function recipeBind(id: string, lineups: (Lineup | undefined)[]): string | null {
  if (!lineups.length || lineups.some((lineup) => !lineup || !practicePosition(lineup))) return null;
  const prefix = `pp_${id.replace(/[^a-zA-Z0-9_]/g, "_").slice(0, 64)}`;
  const steps = lineups.map((lineup, index) => `alias "${prefix}_${index}" "${practicePosition(lineup!)};alias pp_next ${prefix}_${(index + 1) % lineups.length}"`);
  return [...steps, `alias "pp_next" "${prefix}_0"`, 'bind "KP_ENTER" "pp_next"'].join(';');
}
