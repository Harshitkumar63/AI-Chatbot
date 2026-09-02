import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ROLES, ANSWER_MODES } from "../utils/constants";
import SourceCitation from "./SourceCitation";
import TypingIndicator from "./TypingIndicator";

/**
 * MessageBubble Component for Eduzyra AI Assistant.
 *
 * Features:
 * - Rich Markdown rendering with tables, lists, and bold text
 * - Code block rendering with 1-click Copy button
 * - Distinct 3-way Answer Mode Badges (Course Catalog, RAG Docs, General LLM)
 * - Transparent Source Citations
 */
export default function MessageBubble({ message }) {
  const isHuman = message.role === ROLES.HUMAN;
  const isAI = message.role === ROLES.AI;
  const [copiedCodeId, setCopiedCodeId] = useState(null);

  const handleCopyCode = (codeText, id) => {
    navigator.clipboard.writeText(codeText);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  // Helper to render mode label
  const renderModeBadge = () => {
    if (!message.answerMode) return null;

    switch (message.answerMode) {
      case ANSWER_MODES.COURSE_DATA:
        return (
          <div className="message__mode message__mode--course">
            <span className="message__mode-icon">🎓</span>
            <span>Eduzyra Course Catalog</span>
          </div>
        );
      case ANSWER_MODES.RAG:
        return (
          <div className="message__mode message__mode--rag">
            <span className="message__mode-icon">📚</span>
            <span>Knowledge Base</span>
          </div>
        );
      case ANSWER_MODES.DIRECT:
        return (
          <div className="message__mode message__mode--direct">
            <span className="message__mode-icon">💡</span>
            <span>General Knowledge</span>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className={`message ${isHuman ? "message--human" : "message--ai"}`}>
      {/* Avatar */}
      <div className="message__avatar" title={isHuman ? "Student" : "Eduzyra AI"}>
        {isHuman ? "👤" : "✨"}
      </div>

      {/* Body */}
      <div className="message__body">
        <div className="message__content">
          {isHuman ? (
            <p className="message__text-human">{message.content}</p>
          ) : (
            <div className="message__markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeString = String(children).replace(/\n$/, "");
                    const codeId = Math.random().toString(36).substring(2, 9);

                    return !inline ? (
                      <div className="code-block-wrapper">
                        <div className="code-block-header">
                          <span className="code-block-lang">{match ? match[1] : "code"}</span>
                          <button
                            type="button"
                            className="code-block-copy"
                            onClick={() => handleCopyCode(codeString, codeId)}
                          >
                            {copiedCodeId === codeId ? "✓ Copied!" : "📋 Copy"}
                          </button>
                        </div>
                        <pre className="code-block-pre">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      </div>
                    ) : (
                      <code className="inline-code" {...props}>
                        {children}
                      </code>
                    );
                  },
                  table({ children }) {
                    return (
                      <div className="table-responsive">
                        <table className="markdown-table">{children}</table>
                      </div>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {message.isStreaming && <TypingIndicator />}
        </div>

        {/* Answer mode indicator badge (AI messages only) */}
        {isAI && renderModeBadge()}

        {/* Structured Source Citations */}
        {isAI && !message.isStreaming && message.sources && message.sources.length > 0 && (
          <SourceCitation sources={message.sources} answerMode={message.answerMode} />
        )}

        {/* Timestamp */}
        <div className="message__time">
          {new Date(message.created_at || Date.now()).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
