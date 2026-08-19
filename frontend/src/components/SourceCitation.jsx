/**
 * Source citation component.
 *
 * Displays the documents that were used to generate the AI's response.
 * Now includes optional confidence scores for transparency.
 */
export default function SourceCitation({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="source-citation">
      <div className="source-citation__header">
        <span className="source-citation__icon">📚</span>
        <span className="source-citation__label">Sources</span>
      </div>
      <div className="source-citation__list">
        {sources.map((source, index) => (
          <div key={index} className="source-citation__item">
            <span className="source-citation__doc">📄 {source.document}</span>
            {source.page && (
              <span className="source-citation__page">Page {source.page}</span>
            )}
            {source.confidence_score != null && (
              <span className="source-citation__score">
                {Math.round(source.confidence_score * 100)}% match
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
