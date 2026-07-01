export default function TopThree({ top3, imageByName, onSelect }) {
  if (top3.length === 0) return null;

  return (
    <div className="top3">
      <h2>本日の流行ポケモン TOP3</h2>
      <div className="top3-cards">
        {top3.map(([name, score], i) => (
          <button
            key={name}
            type="button"
            className="top3-card"
            onClick={() => onSelect(name)}
          >
            <div className="top3-rank">{i + 1}</div>
            {imageByName[name] ? (
              <img className="top3-icon" src={imageByName[name]} alt={name} />
            ) : (
              <div className="top3-icon top3-icon-placeholder" />
            )}
            <div className="top3-name">{name}</div>
            <div className="top3-score">{score.toFixed(0)}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
