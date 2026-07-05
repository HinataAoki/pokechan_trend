const TYPE_BADGES = {
  rental: { label: "レンタル配布", className: "type-badge-rental" },
  build: { label: "構築紹介", className: "type-badge-build" },
  counter: { label: "対策解説", className: "type-badge-counter" },
  battle: { label: "対戦動画", className: "type-badge-battle" },
};

export default function ContributionModal({ date, pokemonName, videos, loading, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{pokemonName ? `${date} の ${pokemonName} に影響した動画` : `${date} に影響した動画`}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="閉じる">
            ×
          </button>
        </div>

        {loading && <p>読み込み中...</p>}

        {!loading && videos.length === 0 && <p>影響した動画は見つかりませんでした。</p>}

        {!loading && videos.length > 0 && (
          <ul className="contribution-list">
            {videos.map((v) => {
              const badge = TYPE_BADGES[v.video_type];
              return (
                <li key={`${v.video_id}-${v.pokemon_name}`}>
                  <a href={v.youtube_url} target="_blank" rel="noreferrer">
                    {v.video_title}
                  </a>
                  <div className="contribution-meta">
                    {badge && <span className={`type-badge ${badge.className}`}>{badge.label}</span>}
                    {!pokemonName && <span>{v.pokemon_name} / </span>}
                    投稿日: {v.published_at.slice(0, 10)} / 影響度: {v.contribution_score.toFixed(0)}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
