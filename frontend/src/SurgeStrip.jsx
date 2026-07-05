// "Rising on YouTube" picks: pokemon whose share of the day's influence
// score rose the most vs 3 days earlier (computed in export_snapshot.py).
// Backtested at ~2x the base rate for upcoming rank risers - shown as a
// hint, not a ranking.
export default function SurgeStrip({ surges, dates, today, imageByName, onSelect }) {
  // Prefer tomorrow's (the forecast day's) surge picks; fall back to today.
  const forecastDate = dates.find((d) => d > today);
  const date = surges[forecastDate]?.length ? forecastDate : today;
  const names = surges[date] ?? [];
  if (names.length === 0) return null;

  return (
    <section className="surge">
      <h2>
        <span className="surge-flame" aria-hidden="true">
          ▲
        </span>
        急上昇ピックアップ
        <span className="surge-note">動画発で勢いが伸びているポケモン</span>
      </h2>
      <div className="surge-cards">
        {names.map((name) => (
          <button key={name} type="button" className="surge-card" onClick={() => onSelect(date, name)}>
            {imageByName[name] ? (
              <img className="surge-icon" src={imageByName[name]} alt="" />
            ) : (
              <span className="surge-icon surge-icon-placeholder" />
            )}
            <span className="surge-name">{name}</span>
            <span className="surge-badge">急上昇</span>
          </button>
        ))}
      </div>
    </section>
  );
}
