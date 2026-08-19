import { APP_NAME, APP_TAGLINE } from "../utils/constants";

/**
 * Chat header with app branding and new chat button.
 */
export default function ChatHeader({ onNewChat }) {
  return (
    <header className="chat-header">
      <div className="chat-header__brand">
        <div className="chat-header__icon">🤖</div>
        <div className="chat-header__text">
          <h1 className="chat-header__title">{APP_NAME}</h1>
          <p className="chat-header__tagline">{APP_TAGLINE}</p>
        </div>
      </div>

      <div className="chat-header__actions">
        <button
          className="chat-header__btn chat-header__btn--new"
          onClick={onNewChat}
          title="Start a new conversation"
        >
          <span className="chat-header__btn-icon">+</span>
          New Chat
        </button>
      </div>
    </header>
  );
}
