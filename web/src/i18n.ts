import { useSyncExternalStore } from "react";
import en from "./i18n/en.json";
import zh from "./i18n/zh.json";

export type Lang = "zh" | "en";

type LocaleTree = { [key: string]: string | LocaleTree };

const DICTS: Record<Lang, LocaleTree> = { zh, en };
const STORAGE_KEY = "cs2-pro-playbook.lang";
const listeners = new Set<() => void>();

function readStoredLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "zh" || stored === "en") return stored;
  } catch {
    // Private mode or a blocked storage API: fall back to the default.
  }
  return "zh";
}

let current: Lang = readStoredLang();

function applyDocumentLang(lang: Lang): void {
  try {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  } catch {
    // Not fatal: the UI still switches, only the document metadata is missed.
  }
}

applyDocumentLang(current);

export function getLang(): Lang {
  return current;
}

export function setLang(lang: Lang): void {
  if (lang === current) return;
  current = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // The switch still works for this session; persistence is best effort.
  }
  applyDocumentLang(lang);
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useLang(): Lang {
  return useSyncExternalStore(subscribe, getLang, getLang);
}

function lookup(tree: LocaleTree, path: string[]): string | undefined {
  let node: string | LocaleTree | undefined = tree;
  for (const part of path) {
    if (typeof node !== "object" || node === null) return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

/** Dot-path lookup; a missing key returns the key itself instead of throwing. */
export function t(key: string, vars?: Record<string, string | number>): string {
  const value = lookup(DICTS[current], key.split("."));
  if (value === undefined) return key;
  if (!vars) return value;
  return value.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match,
  );
}

/** Translate a demo place name for a map, falling back to the raw name. */
export function calloutLabel(map: string, name: string | null | undefined): string {
  if (!name) return "—";
  const key = `callout.${map}.${name}`;
  const label = t(key);
  return label === key ? name : label;
}
