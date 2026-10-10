/**
 * Singleton API Client to handle all backend communication with FastAPI.
 */

// Force IPv4 loopback to avoid Windows Node/Browser IPv6 resolution issues with uvicorn
const API_BASE = "http://127.0.0.1:8000";

const TOKEN_KEY = "omniops_auth_token";
const FALLBACK_TOKEN_KEY = "omniops_jwt_token";

export interface UserInfo {
  user_id: string;
  email: string;
  is_active: boolean;
  name?: string;
  designation?: string;
  created_at?: string;
  profile?: UserProfileInfo | null;
}

export interface UserProfileInfo {
  user_id: string;
  name: string;
  skill_set: string[];
  designation: string;
  refinery_experience_level: "beginner" | "intermediate" | "advanced" | "expert";
  preferred_explanation_depth: "concise" | "moderate" | "detailed";
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export class ApiClient {
  static getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(FALLBACK_TOKEN_KEY);
  }

  static setToken(token: string | null): void {
    if (typeof window === "undefined") return;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(FALLBACK_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(FALLBACK_TOKEN_KEY);
    }
  }

  static clearToken(): void {
    this.setToken(null);
  }

  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    
    // Add default headers if not provided and it's not FormData
    const headers = new Headers(options.headers || {});
    if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    // Attach Bearer token if present
    const token = this.getToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    try {
      const response = await fetch(url, { ...options, headers });
      
      if (!response.ok) {
        if (response.status === 401) {
          this.clearToken();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("omniops:unauthorized"));
          }
        }

        let errorMsg = response.statusText;
        try {
          const errData = await response.json();
          errorMsg = errData.detail || errorMsg;
        } catch {
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

  // --- Auth & Profile API ---

  static async register(data: {
    email: string;
    password: string;
    name?: string;
    designation?: string;
    skill_set?: string[];
    refinery_experience_level?: string;
    preferred_explanation_depth?: string;
  }): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  static async login(credentials: { email: string; password: string }): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  static async getCurrentUser(): Promise<UserInfo> {
    return this.request<UserInfo>("/auth/me");
  }

  static async getProfile(): Promise<UserProfileInfo> {
    return this.request<UserProfileInfo>("/profile");
  }

  static async updateProfile(data: {
    name?: string;
    designation?: string;
    skill_set?: string[];
    refinery_experience_level?: string;
    preferred_explanation_depth?: string;
  }): Promise<UserProfileInfo> {
    return this.request<UserProfileInfo>("/profile", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  static logout(): void {
    this.clearToken();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("omniops:unauthorized"));
    }
  }

  // --- Core Knowledge and Document API ---

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

  static async query(
    text: string, 
    documentIds: string[] | null = null, 
    sessionId: string | null = null,
    imageBase64?: string | null,
    imageFilename?: string | null
  ) {
    return this.request<any>("/query", {
      method: "POST",
      body: JSON.stringify({ 
        query: text, 
        document_ids: documentIds, 
        session_id: sessionId,
        image_base64: imageBase64,
        image_filename: imageFilename,
      }),
    });
  }

  static async queryStream(
    text: string, 
    documentIds: string[] | null = null, 
    sessionId: string | null = null, 
    onEvent: (event: any) => void,
    imageBase64?: string | null,
    imageFilename?: string | null
  ) {
    const url = `${API_BASE}/query/stream`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ 
        query: text, 
        document_ids: documentIds, 
        session_id: sessionId,
        image_base64: imageBase64,
        image_filename: imageFilename,
      }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.clearToken();
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("omniops:unauthorized"));
        }
      }
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
