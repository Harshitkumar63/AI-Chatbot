import { useRef, useEffect, useState } from "react";
import ChatHeader from "./ChatHeader";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import { useChat } from "../hooks/useChat";
import { APP_NAME } from "../utils/constants";

/**
 * Main chat window component.
 *
 * Students only see the chat interface — no file upload.
 * Document management is admin-only (via API).
 */
export default function ChatWindow() {
  const {
    messages,
    conversationId,
    isStreaming,
    error,
    send,
    newConversation,
  } = useChat();

  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      <ChatHeader onNewChat={newConversation} />

      {/* Messages Area */}
      <div className="chat-window__messages" id="messages-container">
        {messages.length === 0 ? (
          <div className="chat-window__empty">
            <div className="chat-window__empty-icon">🤖</div>
            <h2 className="chat-window__empty-title">
              Welcome to {APP_NAME}!
            </h2>
            <p className="chat-window__empty-text">
              I&apos;m your AI learning assistant. Ask me anything — I can answer
              from general knowledge or from our knowledge base documents!
            </p>
            <div className="chat-window__suggestions">
              {[
                "What is machine learning?",
                "Explain Newton's Second Law",
                "Write a Python program for Binary Search",
                "What courses are available?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  className="chat-window__suggestion"
                  onClick={() => send(suggestion)}
                  disabled={isStreaming}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {/* Error display */}
        {error && (
          <div className="chat-window__error">
            <span>⚠️ {error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={send} disabled={isStreaming} />
    </div>
  );
}
