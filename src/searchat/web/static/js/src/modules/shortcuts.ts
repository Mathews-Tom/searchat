/** Keyboard shortcuts — registered via Alpine @keydown.window or direct listeners. */

import Alpine from "alpinejs";

interface ShortcutDef {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  description: string;
  action: () => void;
}

const shortcuts: ShortcutDef[] = [
  {
    key: "k",
    meta: true,
    description: "Focus search",
    action: () => {
      const el = document.getElementById("search") as HTMLInputElement | null;
      el?.focus();
      el?.select();
    },
  },
  {
    key: "k",
    ctrl: true,
    description: "Focus search",
    action: () => {
      const el = document.getElementById("search") as HTMLInputElement | null;
      el?.focus();
      el?.select();
    },
  },
  {
    key: "Escape",
    description: "Close modal / blur search",
    action: () => {
      const store = Alpine.store("layout") as { helpModalOpen: boolean };
      if (store.helpModalOpen) {
        store.helpModalOpen = false;
        return;
      }
      const active = document.activeElement as HTMLElement | null;
      active?.blur();
    },
  },
  {
    key: "/",
    description: "Focus search (vim-style)",
    action: () => {
      const active = document.activeElement;
      if (
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement
      ) {
        return; // Don't hijack when typing
      }
      const el = document.getElementById("search") as HTMLInputElement | null;
      el?.focus();
      el?.select();
    },
  },
  {
    key: "?",
    shift: true,
    description: "Toggle help modal",
    action: () => {
      const active = document.activeElement;
      if (
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement
      ) {
        return;
      }
      const store = Alpine.store("layout") as { helpModalOpen: boolean };
      store.helpModalOpen = !store.helpModalOpen;
    },
  },
];

function matchShortcut(e: KeyboardEvent, s: ShortcutDef): boolean {
  if (e.key !== s.key) return false;
  if (s.ctrl && !e.ctrlKey) return false;
  if (s.meta && !e.metaKey) return false;
  if (s.shift && !e.shiftKey) return false;
  // Don't fire ctrl/meta shortcuts if not expected
  if (!s.ctrl && !s.meta && (e.ctrlKey || e.metaKey)) return false;
  return true;
}

export function initShortcuts(): void {
  document.addEventListener("keydown", (e: KeyboardEvent) => {
    for (const s of shortcuts) {
      if (matchShortcut(e, s)) {
        e.preventDefault();
        s.action();
        return;
      }
    }
  });
}
