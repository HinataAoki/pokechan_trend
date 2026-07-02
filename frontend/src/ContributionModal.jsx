export default function ContributionModal({ date, videos, loading, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>
          ×
        </button>
        <h3>{date} に影響を与えた動画</h3>

        {loading && <p>読み込み中...</p>}

        {!loading && videos.length === 0 && <p>この日に影響した動画は見つかりませんでした。</p>}

        {!loading && videos.length > 0 && (
          <ul className="contribution-list">
            {videos.map((v) => (
              <li key={`${v.video_id}-${v.pokemon_name}`}>
                <a href={v.youtube_url} target="_blank" rel="noreferrer">
                  {v.video_title}
                </a>
                <div className="contribution-meta">
                  {v.pokemon_name} / 投稿日: {v.published_at.slice(0, 10)} / 影響度:{" "}
                  {v.contribution_score.toFixed(0)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
