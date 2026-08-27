import { APP_NAME, APP_TAGLINE } from "../utils/constants";

/**
 * ChatHeader Component for Eduzyra AI Assistant.
 *
 * Features:
 * - Brand logo & live pulse indicator
 * - 3-Way capability badges (Courses, RAG Docs, General AI)
 * - Quick action New Chat button
 */
export default function ChatHeader({ onNewChat }) {
  return (
    <header className="chat-header">
      <div className="chat-header__brand">
        <div className="chat-header__icon-wrapper">
          <span className="chat-header__icon">✨</span>
          <span className="chat-header__status-pulse" title="System Online" />
        </div>
        <div className="chat-header__text">
          <div className="chat-header__title-row">
            <h1 className="chat-header__title">{APP_NAME}</h1>
            <span className="chat-header__badge">Hybrid AI</span>
          </div>
          <p className="chat-header__tagline">{APP_TAGLINE}</p>
        </div>
      </div>

      <div className="chat-header__capabilities">
        <span className="capability-pill" title="Live course catalog and syllabus queries">
          🎓 Courses
        </span>
        <span className="capability-pill" title="Verified knowledge base search">
          📚 Docs
        </span>
        <span className="capability-pill" title="General coding, math & science explanations">
          💡 General
        </span>
      </div>

      <div className="chat-header__actions">
        <button
          type="button"
          className="chat-header__btn chat-header__btn--new"
          onClick={onNewChat}
          title="Start a fresh conversation"
        >
          <span className="chat-header__btn-icon">＋</span>
          <span>New Chat</span>
        </button>
      </div>
    </header>
  );
}
