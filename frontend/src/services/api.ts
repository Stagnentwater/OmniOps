/**
 * Singleton API Client to handle all backend communication with FastAPI.
 */

// Force IPv4 loopback to avoid Windows Node/Browser IPv6 resolution issues with uvicorn locally
// Use NEXT_PUBLIC_API_URL in production (e.g., Vercel)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ApiClient {
  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    
    // Add default headers if not provided and it's not FormData
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    try {
      const response = await fetch(url, { ...options, headers });
      
      if (!response.ok) {
        let errorMsg = response.statusText;
        try {
          const errData = await response.json();
          errorMsg = errData.detail || errorMsg;
        } catch (e) {
          // ignore
        }
        throw new Error(`API Error ${response.status}: ${errorMsg}`);
      }
      
      // Return raw response for streaming endpoints
      if (options.headers && (options.headers as Record<string, string>)["Accept"] === "application/pdf") {
        return response.blob() as any;
      }
      
      return response.json() as Promise<T>;
    } catch (error) {
      console.error(`[ApiClient] Failed fetching ${url}:`, error);
      throw error;
    }
  }

  static async getHealth() {
    return this.request<any>("/health");
  }

  static async getDocuments() {
    return this.request<{documents: any[]}>("/documents");
  }

  static async getDocument(id: string) {
    return this.request<any>(`/documents/${id}`);
  }

  static async getDocumentStatus(id: string) {
    return this.request<any>(`/documents/${id}/status`);
  }

  static async getDocumentContentUrl(id: string) {
    // We return the raw URL for the iframe to load the PDF
    return `${API_BASE}/documents/${id}/content`;
  }

  static getDocumentStreamUrl(id: string) {
    // Return the URL for EventSource to consume SSE
    return `${API_BASE}/documents/${id}/stream`;
  }

  static async getKnowledgeStatistics() {
    return this.request<any>("/knowledge/statistics");
  }

  static async getKnowledgeGraph() {
    return this.request<any>("/knowledge/graph");
  }

  static async getSystemStatus() {
    return this.request<{status: string}>("/knowledge/status");
  }

  static async uploadDocument(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return this.request<any>("/uploads", {
      method: "POST",
      body: formData,
    });
  }

  static async deleteDocument(id: string) {
    return this.request<any>(`/documents/${id}`, { method: "DELETE" });
  }

  static async query(text: string, documentIds: string[] | null = null, sessionId: string | null = null) {
    return this.request<any>("/query", {
      method: "POST",
      body: JSON.stringify({ query: text, document_ids: documentIds, session_id: sessionId }),
    });
  }

  static async queryStream(text: string, documentIds: string[] | null = null, sessionId: string | null = null, onEvent: (event: any) => void) {
    const url = `${API_BASE}/query/stream`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, document_ids: documentIds, session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error(`Stream Error ${response.status}`);
    }

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || ""; // Keep the incomplete part

      for (const part of parts) {
        if (part.startsWith("data: ")) {
          const dataStr = part.replace("data: ", "").trim();
          if (dataStr) {
            try {
              const event = JSON.parse(dataStr);
              onEvent(event);
            } catch (err) {
              console.error("Failed to parse SSE JSON:", dataStr);
            }
          }
        }
      }
    }
  }

  // --- Chat History API ---

  static async getChatSessions() {
    return this.request<any[]>("/chat/sessions");
  }

  static async createChatSession() {
    return this.request<{session_id: string}>("/chat/sessions", { method: "POST" });
  }

  static async getChatMessages(sessionId: string) {
    return this.request<any[]>(`/chat/sessions/${sessionId}`);
  }

  static async deleteChatSession(sessionId: string) {
    return this.request<any>(`/chat/sessions/${sessionId}`, { method: "DELETE" });
  }
}
