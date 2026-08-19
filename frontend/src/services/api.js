/*
 * API Service for EduBot Frontend.
 *
 * This module handles all communication with the backend API.
 * It abstracts fetch/SSE calls so components don't deal with HTTP details.
 */

// Backend API base URL — loaded from environment variables
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

/**
 * Send a chat message and receive a streaming SSE response.
 *
 * This uses the Fetch API with streaming to read Server-Sent Events.
 *
 * @param {string} message - The user's message
 * @param {string|null} conversationId - Existing conversation ID (null for new)
 * @param {function} onToken - Callback for each token received
 * @param {function} onStart - Callback when streaming starts (receives conversationId)
 * @param {function} onMode - Callback when answer mode is determined (receives "rag" or "direct")
 * @param {function} onSources - Callback when source citations are received
 * @param {function} onEnd - Callback when streaming completes
 * @param {function} onError - Callback for errors
 */
export async function sendMessage({
  message,
  conversationId = null,
  onToken,
  onStart,
  onMode,
  onSources,
  onEnd,
  onError,
}) {
  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }

    // Read the SSE stream using ReadableStream API
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Decode the chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE events (separated by double newlines)
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        // SSE format: "data: {...json...}"
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const jsonStr = trimmed.slice(5).trim(); // Remove "data: " prefix
        if (!jsonStr || jsonStr === "[DONE]") continue;

        try {
          const event = JSON.parse(jsonStr);

          switch (event.event) {
            case "start":
              onStart?.(event.conversation_id);
              break;
            case "mode":
              onMode?.(event.answer_mode || null);
              break;
            case "token":
              onToken?.(event.token);
              break;
            case "sources":
              onSources?.(event.sources || [], event.answer_mode || null);
              break;
            case "error":
              onError?.(event.error || "Unknown error");
              break;
            case "end":
              onEnd?.();
              break;
          }
        } catch {
          // Skip malformed JSON lines
        }
      }
    }
  } catch (error) {
    onError?.(error.message || "Failed to connect to the server");
  }
}

/**
 * Get all conversations.
 *
 * @returns {Promise<Array>} List of conversations
 */
export async function getConversations() {
  const response = await fetch(`${API_BASE}/conversations`);

  if (!response.ok) throw new Error("Failed to load conversations");

  return response.json();
}

/**
 * Get a specific conversation with all messages.
 *
 * @param {string} conversationId - The conversation ID
 * @returns {Promise<object>} Conversation with messages
 */
export async function getConversation(conversationId) {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`);

  if (!response.ok) throw new Error("Failed to load conversation");

  return response.json();
}

/**
 * Get all uploaded documents.
 *
 * @returns {Promise<Array>} List of documents
 */
export async function getDocuments() {
  const response = await fetch(`${API_BASE}/documents`);

  if (!response.ok) throw new Error("Failed to load documents");

  return response.json();
}

/**
 * Check the backend health.
 *
 * @returns {Promise<object>} Health status
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);

  if (!response.ok) throw new Error("Backend is not responding");

  return response.json();
}
