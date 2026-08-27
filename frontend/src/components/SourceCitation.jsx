import { useState } from "react";

/**
 * Enhanced Source Citation Component for Eduzyra.
 *
 * Supports structured citations for:
 * 1. 🎓 Eduzyra Course Catalog (Live Database)
 * 2. 📚 Knowledge Base Documents (PDF, DOCX, TXT with Page & Section)
 * 3. 💡 General Educational Knowledge
 */
export default function SourceCitation({ sources, answerMode }) {
  const [expandedIndex, setExpandedIndex] = useState(null);

  if (!sources || sources.length === 0) {
    if (answerMode === "direct") {
      return (
        <div className="source-citation source-citation--direct">
          <span className="source-citation__badge source-citation__badge--direct">
            💡 General Educational Knowledge
          </span>
        </div>
      );
    }
    return null;
  }

  const toggleExpand = (index) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <div className="source-citation">
      <div className="source-citation__header">
        <span className="source-citation__icon">
          {answerMode === "course_data" ? "🎓" : "📚"}
        </span>
        <span className="source-citation__label">
          {answerMode === "course_data" ? "Live Course Catalog" : "Verified Sources"}
        </span>
      </div>

      <div className="source-citation__list">
        {sources.map((source, index) => {
          const isCourse = source.source_type === "course_catalog" || source.document.includes("Course Catalog");
          const isExpanded = expandedIndex === index;

          return (
            <div
              key={index}
              className={`source-citation__card ${isCourse ? "source-citation__card--course" : ""}`}
            >
              <div
                className="source-citation__card-header"
                onClick={() => source.chunk_preview && toggleExpand(index)}
                style={{ cursor: source.chunk_preview ? "pointer" : "default" }}
                title={source.chunk_preview ? "Click to view preview snippet" : ""}
              >
                <span className="source-citation__doc">
                  {isCourse ? "🎓" : "📄"} {source.document}
                </span>

                <div className="source-citation__meta">
                  {source.page && (
                    <span className="source-citation__badge source-citation__badge--page">
                      Page {source.page}
                    </span>
                  )}
                  {source.section && (
                    <span className="source-citation__badge source-citation__badge--section">
                      {source.section}
                    </span>
                  )}
                  {source.confidence_score != null && !isCourse && (
                    <span className="source-citation__score">
                      {Math.round(source.confidence_score * 100)}% match
                    </span>
                  )}
                  {isCourse && (
                    <span className="source-citation__live-dot">● Live Data</span>
                  )}
                  {source.chunk_preview && (
                    <span className="source-citation__toggle">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  )}
                </div>
              </div>

              {/* Collapsible Chunk Preview */}
              {isExpanded && source.chunk_preview && (
                <div className="source-citation__preview">
                  <div className="source-citation__preview-label">Content Excerpt:</div>
                  <p>{source.chunk_preview}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
