/**
 * Singleton API Client to handle all backend communication with FastAPI.
 */

// Force IPv4 loopback to avoid Windows Node/Browser IPv6 resolution issues with uvicorn
const API_BASE = "http://127.0.0.1:8001";

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

  static async query(text: string, documentIds: string[] | null = null) {
    return this.request<any>("/query", {
      method: "POST",
      body: JSON.stringify({ query: text, document_ids: documentIds }),
    });
  }
}
