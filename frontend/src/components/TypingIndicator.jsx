/**
 * Animated typing indicator (three bouncing dots).
 *
 * Shown while the AI is generating a response.
 */
export default function TypingIndicator() {
  return (
    <span className="typing-indicator">
      <span className="typing-indicator__dot"></span>
      <span className="typing-indicator__dot"></span>
      <span className="typing-indicator__dot"></span>
    </span>
  );
}
