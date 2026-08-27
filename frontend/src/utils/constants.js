/**
 * Constants for Eduzyra AI Assistant Frontend.
 */

export const APP_NAME = "Eduzyra AI";
export const APP_TAGLINE = "Hybrid AI Learning & Course Assistant";

// Message roles
export const ROLES = {
  HUMAN: "human",
  AI: "ai",
  SYSTEM: "system",
};

// 3-Way Answer Modes
export const ANSWER_MODES = {
  COURSE_DATA: "course_data",
  RAG: "rag",
  DIRECT: "direct",
  HYBRID: "hybrid",
};

// Maximum file size for admin uploads (10MB)
export const MAX_FILE_SIZE = 10 * 1024 * 1024;

// Accepted file types (matches backend supported formats)
export const ACCEPTED_FILE_TYPES = ".pdf,.docx,.txt";
