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
import { initCodeCopy } from "@modules/code-copy";
import { rebuildProgress } from "@modules/rebuild-progress";

// Expose Alpine globally for x-data attribute access
(window as unknown as { Alpine: typeof Alpine }).Alpine = Alpine;

// Register Alpine stores
Alpine.store("theme", themeStore);
Alpine.store("search", searchStore);
Alpine.store("layout", layoutStore);
Alpine.store("chat", chatStore);
Alpine.store("dataset", datasetStore);

// Register Alpine data components
Alpine.data("rebuildProgress", rebuildProgress);

// Start Alpine
Alpine.start();

// Restore the legacy page bootstrap that still owns the live
// search/manage/conversation interactions. The templates load only the
// bundled dist entrypoint, so it needs to pull in that behavior layer.
void import("../main.js").catch((err) => {
  console.error("Legacy web bootstrap failed:", err);
});

// Initialize non-Alpine modules still owned by the bundle.
initCodeCopy();

// Re-initialize code copy buttons after HTMX swaps in new content
document.addEventListener("htmx:afterSwap", () => {
  initCodeCopy();
});
