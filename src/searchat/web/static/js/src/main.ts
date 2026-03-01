/**
 * Searchat Frontend — Alpine.js store registration and initialization.
 *
 * This is the single entry point bundled by esbuild into dist/main.js.
 * Each Alpine store is imported and registered here; HTMX handles
 * server-driven UI updates, Alpine handles client-side reactivity.
 */

import Alpine from "alpinejs";
import "htmx.org";
import { themeStore } from "@stores/theme";
import { searchStore } from "@stores/search";
import { layoutStore } from "@stores/layout";
import { chatStore } from "@stores/chat";
import { datasetStore } from "@stores/dataset";
import { initShortcuts } from "@modules/shortcuts";
import { initCodeCopy } from "@modules/code-copy";

// Expose Alpine globally for x-data attribute access
(window as unknown as { Alpine: typeof Alpine }).Alpine = Alpine;

// Register Alpine stores
Alpine.store("theme", themeStore);
Alpine.store("search", searchStore);
Alpine.store("layout", layoutStore);
Alpine.store("chat", chatStore);
Alpine.store("dataset", datasetStore);

// Start Alpine
Alpine.start();

// Initialize non-Alpine modules
initShortcuts();
initCodeCopy();

// Re-initialize code copy buttons after HTMX swaps in new content
document.addEventListener("htmx:afterSwap", () => {
  initCodeCopy();
});

// Splash screen — show on first visit per server start.
// splash.js is served as a static file (not bundled) so use an absolute URL
// to avoid esbuild emitting it as a chunk that maps to the wrong path.
async function initSplash(): Promise<void> {
  try {
    const splash = await import(/* @vite-ignore */ "/static/js/splash.js");
    if (typeof splash.checkAndShowSplash === "function") {
      await splash.checkAndShowSplash();
    }
  } catch (err) {
    console.warn("Splash init skipped:", err);
  }
}

window.addEventListener("load", () => {
  initSplash();
});
