/** Alpine.js chat store — manages chat state and streaming responses. */

export const chatStore = {
  provider: "ollama",
  model: "",
  temperature: null as number | null,
  maxTokens: null as number | null,
  systemPrompt: "",
  query: "",
  answer: "",
  status: "",
  sending: false,
  sources: [] as Array<{
    conversation_id: string;
    title: string;
    score: number;
    snippet: string;
  }>,
  controller: null as AbortController | null,

  init() {
    const saved = localStorage.getItem("chatProvider");
    if (saved) this.provider = saved;
    const savedModel = localStorage.getItem("chatModel");
    if (savedModel) this.model = savedModel;
  },

  setProvider(provider: string) {
    this.provider = provider;
    localStorage.setItem("chatProvider", provider);
  },

  setModel(model: string) {
    this.model = model;
    localStorage.setItem("chatModel", model);
  },

  async send() {
    if (!this.query.trim() || this.sending) return;

    this.sending = true;
    this.answer = "";
    this.sources = [];
    this.status = "Searching for relevant context...";
    this.controller = new AbortController();

    const body: Record<string, unknown> = { query: this.query };
    if (this.provider) body.provider = this.provider;
    if (this.model) body.model = this.model;
    if (this.temperature !== null) body.temperature = this.temperature;
    if (this.maxTokens !== null) body.max_tokens = this.maxTokens;
    if (this.systemPrompt) body.system_prompt = this.systemPrompt;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: this.controller.signal,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      this.status = "Generating response...";

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") continue;

          try {
            const parsed = JSON.parse(data);
            if (parsed.type === "token") {
              this.answer += parsed.content;
            } else if (parsed.type === "sources") {
              this.sources = parsed.sources;
            } else if (parsed.type === "status") {
              this.status = parsed.message;
            }
          } catch {
            // Skip malformed SSE lines
          }
        }
      }

      this.status = "";
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        this.status = "Stopped";
      } else {
        this.status = `Error: ${err instanceof Error ? err.message : String(err)}`;
      }
    } finally {
      this.sending = false;
      this.controller = null;
    }
  },

  stop() {
    if (this.controller) {
      this.controller.abort();
    }
  },

  clear() {
    this.query = "";
    this.answer = "";
    this.sources = [];
    this.status = "";
    this.sending = false;
  },
};
