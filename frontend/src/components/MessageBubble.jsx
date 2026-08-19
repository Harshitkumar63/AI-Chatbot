import { ROLES } from "../utils/constants";
import SourceCitation from "./SourceCitation";
import TypingIndicator from "./TypingIndicator";

/**
 * Individual chat message bubble.
 *
 * Now shows answer mode indicator (RAG vs General Knowledge)
 * for AI messages after streaming completes.
 */
export default function MessageBubble({ message }) {
  const isHuman = message.role === ROLES.HUMAN;
  const isAI = message.role === ROLES.AI;

  return (
    <div className={`message ${isHuman ? "message--human" : "message--ai"}`}>
      {/* Avatar */}
      <div className="message__avatar">
        {isHuman ? "👤" : "🤖"}
      </div>

      {/* Content */}
      <div className="message__body">
        <div className="message__content">
          {message.content}
          {message.isStreaming && <TypingIndicator />}
        </div>

        {/* Answer mode indicator (AI messages only, after streaming) */}
        {isAI && !message.isStreaming && message.answerMode && (
          <div
            className={`message__mode message__mode--${message.answerMode}`}
          >
            {message.answerMode === "rag" ? (
              <>📚 Answered from knowledge base</>
            ) : (
              <>💡 Answered from general knowledge</>
            )}
          </div>
        )}

        {/* Source citations (RAG mode, AI messages only) */}
        {isAI && message.sources && message.sources.length > 0 && (
          <SourceCitation sources={message.sources} />
        )}

        {/* Timestamp */}
        <div className="message__time">
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
