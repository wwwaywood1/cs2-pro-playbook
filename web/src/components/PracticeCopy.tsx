import { useEffect, useRef, useState } from "react";
import { copyText } from "../practice";
import { t } from "../i18n";

export default function PracticeCopy({ command, label, tip }: { command: string | null; label: string; tip: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "manual">("idle");
  const timer = useRef<number>();
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; window.clearTimeout(timer.current); }; }, []);
  useEffect(() => { setStatus("idle"); window.clearTimeout(timer.current); }, [command]);
  return <span className="practice-bind"><button type="button" className="button button-ghost" disabled={!command} title={command ? `${tip}（KP_ENTER）` : "缺少起投位置，暂无法生成练习脚本"} onClick={async (event) => {
    event.stopPropagation();
    if (!command) return;
    const copied = await copyText(command, null);
    if (!alive.current) return;
    setStatus(copied ? "copied" : "manual");
    window.clearTimeout(timer.current);
    if (copied) timer.current = window.setTimeout(() => setStatus("idle"), 1500);
  }}>{status === "copied" ? t("ui.copied") : label}</button>{status === "manual" ? <code tabIndex={0} className="practice-cmd">{command}</code> : null}<span className="sr-only" role="status">{status === "manual" ? "复制未完成，请手动复制练习脚本" : status === "copied" ? t("ui.copied") : ""}</span></span>;
}
