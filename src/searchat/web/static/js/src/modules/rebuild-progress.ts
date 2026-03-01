/**
 * Alpine.js data component for SSE-driven rebuild progress.
 *
 * Used by the rebuild-progress.html template — connects to an SSE endpoint,
 * updates a progress bar in real time, and redirects to the final view on completion.
 */

declare const htmx: { ajax: (method: string, url: string, opts: Record<string, unknown>) => void };

interface ProgressEvent {
  phase: string;
  current: number;
  total: number;
  pct: number;
}

interface DoneEvent {
  message: string;
}

export function rebuildProgress(streamUrl: string, doneUrl?: string) {
  return {
    phase: "Initializing...",
    current: 0,
    total: 0,
    pct: -1,
    done: false,
    message: "",
    _es: null as EventSource | null,

    start() {
      this._es = new EventSource(streamUrl);

      this._es.addEventListener("progress", (e: MessageEvent) => {
        const d: ProgressEvent = JSON.parse(e.data);
        this.phase = d.phase;
        this.current = d.current;
        this.total = d.total;
        this.pct = d.pct;
      });

      this._es.addEventListener("done", (e: MessageEvent) => {
        const d: DoneEvent = JSON.parse(e.data);
        this.phase = "Done";
        this.pct = 100;
        this.done = true;
        this.message = d.message;
        this._es?.close();

        if (doneUrl) {
          setTimeout(() => {
            htmx.ajax("GET", doneUrl, { target: "#results", swap: "innerHTML" });
          }, 1500);
        }
      });

      this._es.addEventListener("error", () => {
        this._es?.close();
        if (!this.done) {
          this.phase = "Error \u2014 connection lost";
          this.pct = 0;
        }
      });
    },

    destroy() {
      if (this._es) {
        this._es.close();
        this._es = null;
      }
    },
  };
}
