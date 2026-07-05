const RANK_LABELS = ["gold", "silver", "bronze"];

export default function TopThree({ top3, imageByName, surgingNames = [], onSelect }) {
  if (top3.length === 0) return null;
  const surging = new Set(surgingNames);

  return (
    <div className="top3">
      <h2>本日の流行ポケモン TOP3</h2>
      <div className="top3-cards">
        {top3.map(([name, score], i) => (
          <button
            key={name}
            type="button"
            className={`top3-card top3-card-${RANK_LABELS[i]}`}
            onClick={() => onSelect(name)}
          >
            <div className={`top3-rank top3-rank-${RANK_LABELS[i]}`}>{i + 1}</div>
            {surging.has(name) && <div className="top3-surge">急上昇</div>}
            {imageByName[name] ? (
              <img className="top3-icon" src={imageByName[name]} alt={name} />
            ) : (
              <div className="top3-icon top3-icon-placeholder" />
            )}
            <div className="top3-name">{name}</div>
            <div className="top3-score">勢い {score.toFixed(0)}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
