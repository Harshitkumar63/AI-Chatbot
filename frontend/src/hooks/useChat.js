import { useState, useCallback, useRef } from "react";
import { sendMessage } from "../services/api";
import { ROLES } from "../utils/constants";

/**
 * Custom hook for chat functionality.
 *
 * Now handles answer_mode from the stream events to track
 * whether each AI response came from RAG or direct LLM.
 */
export function useChat() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const streamingRef = useRef(false);

  /**
   * Send a message and stream the response.
   */
  const send = useCallback(
    async (text) => {
      if (!text.trim() || streamingRef.current) return;

      setError(null);
      streamingRef.current = true;
      setIsStreaming(true);

      // Add user message immediately
      const userMsg = {
        id: Date.now(),
        role: ROLES.HUMAN,
        content: text,
        created_at: new Date().toISOString(),
      };

      // Add a placeholder for the AI response
      const aiMsg = {
        id: Date.now() + 1,
        role: ROLES.AI,
        content: "",
        sources: [],
        answerMode: null,
        isStreaming: true,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);

      await sendMessage({
        message: text,
        conversationId,
        onStart: (convId) => {
          setConversationId(convId);
        },
        onMode: (answerMode) => {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === ROLES.AI) {
              updated[updated.length - 1] = {
                ...lastMsg,
                answerMode: answerMode || null,
              };
            }
            return updated;
          });
        },
        onToken: (token) => {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === ROLES.AI) {
              updated[updated.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + token,
              };
            }
            return updated;
          });
        },
        onSources: (sources, answerMode) => {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === ROLES.AI) {
              updated[updated.length - 1] = {
                ...lastMsg,
                sources,
                answerMode: answerMode || lastMsg.answerMode || null,
              };
            }
            return updated;
          });
        },
        onEnd: () => {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === ROLES.AI) {
              updated[updated.length - 1] = {
                ...lastMsg,
                isStreaming: false,
              };
            }
            return updated;
          });
          streamingRef.current = false;
          setIsStreaming(false);
        },
        onError: (errMsg) => {
          setError(errMsg);
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === ROLES.AI && !lastMsg.content) {
              updated.pop();
            }
            return updated;
          });
          streamingRef.current = false;
          setIsStreaming(false);
        },
      });
    },
    [conversationId]
  );

  /**
   * Start a new conversation.
   */
  const newConversation = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    setIsStreaming(false);
    streamingRef.current = false;
  }, []);

  /**
   * Load an existing conversation.
   */
  const loadConversation = useCallback((convData) => {
    setConversationId(convData.id);
    setMessages(
      convData.messages.map((msg) => ({
        ...msg,
        isStreaming: false,
      }))
    );
    setError(null);
  }, []);

  return {
    messages,
    conversationId,
    isStreaming,
    error,
    send,
    newConversation,
    loadConversation,
  };
}
