import { useRef, useEffect, useState } from "react";
import ChatHeader from "./ChatHeader";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import { useChat } from "../hooks/useChat";
import { APP_NAME } from "../utils/constants";

/**
 * Main Chat Window Component for Eduzyra.
 *
 * Integrated as a full-featured AI Assistant supporting:
 * - Real-time SSE streaming
 * - 3-Way Hybrid data sources (Course Data, RAG Documents, General LLM)
 * - Markdown & Code block rendering with syntax copy
 * - Error retry mechanism
 */
export default function ChatWindow() {
  const {
    messages,
    isStreaming,
    error,
    send,
    newConversation,
  } = useChat();

  const [lastFailedQuery, setLastFailedQuery] = useState("");
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text) => {
    setLastFailedQuery(text);
    send(text);
  };

  const handleRetry = () => {
    if (lastFailedQuery) {
      send(lastFailedQuery);
    }
  };

  const suggestionCategories = [
    {
      category: "🎓 Course Catalog",
      queries: [
        "What is the price of Python Development?",
        "Who teaches Machine Learning Foundations?",
        "Compare Python Development and Machine Learning",
        "Which course is best for a beginner?",
      ],
    },
    {
      category: "📚 Policies & Documents",
      queries: [
        "What is Eduzyra's refund policy?",
        "What study materials are in the knowledge base?",
      ],
    },
    {
      category: "💡 General Concepts",
      queries: [
        "Explain recursion with a simple example",
        "Write a Python program for Binary Search",
        "Explain Newton's Second Law of Motion",
      ],
    },
  ];

  return (
    <div className="chat-window">
      <ChatHeader onNewChat={newConversation} />

      {/* Messages Scroll Area */}
      <div className="chat-window__messages" id="messages-container">
        {messages.length === 0 ? (
          <div className="chat-window__empty">
            <div className="chat-window__empty-hero">
              <div className="chat-window__empty-icon">✨</div>
              <h2 className="chat-window__empty-title">
                Welcome to {APP_NAME}
              </h2>
              <p className="chat-window__empty-text">
                Your high-speed educational assistant powered by live Eduzyra course data, verified knowledge base documents, and general AI capabilities.
              </p>
            </div>

            {/* Structured Suggestion Grid */}
            <div className="chat-window__suggestion-groups">
              {suggestionCategories.map((group, idx) => (
                <div key={idx} className="suggestion-group">
                  <div className="suggestion-group__title">{group.category}</div>
                  <div className="suggestion-group__items">
                    {group.queries.map((q) => (
                      <button
                        key={q}
                        type="button"
                        className="chat-window__suggestion"
                        onClick={() => handleSend(q)}
                        disabled={isStreaming}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {/* Error Notification with Retry */}
        {error && (
          <div className="chat-window__error">
            <div className="chat-window__error-content">
              <span>⚠️ {error}</span>
              {lastFailedQuery && (
                <button
                  type="button"
                  className="chat-window__retry-btn"
                  onClick={handleRetry}
                  disabled={isStreaming}
                >
                  🔄 Retry
                </button>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
