/** Alpine.js chat store — manages chat state and streaming responses. */

export const chatStore = {
  provider: "ollama",
  model: "",
  sessionId: "",
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
    const savedSessionId = localStorage.getItem("chatSessionId");
    if (savedSessionId) this.sessionId = savedSessionId;
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

    const body: Record<string, unknown> = {
      query: this.query,
      model_provider: this.provider,
    };
    if (this.model) body.model_name = this.model;
    if (this.sessionId) body.session_id = this.sessionId;
    if (this.temperature !== null) body.temperature = this.temperature;
    if (this.maxTokens !== null) body.max_tokens = this.maxTokens;
    if (this.systemPrompt) body.system_prompt = this.systemPrompt;

    try {
      const response = await fetch("/api/chat-rag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: this.controller.signal,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      this.answer = data?.answer ?? "";
      this.sources = Array.isArray(data?.sources) ? data.sources : [];
      if (data?.session_id) {
        this.sessionId = data.session_id;
        localStorage.setItem("chatSessionId", this.sessionId);
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
    this.sessionId = "";
    localStorage.removeItem("chatSessionId");
  },
};
