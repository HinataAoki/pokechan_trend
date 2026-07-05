// Heat levels: cream -> yellow -> orange -> red, pokeball-flavored.
const LEVEL_COLORS = ["#ffffff", "#fff4c2", "#ffe08a", "#ffb85c", "#ff8a5c"];

function levelForRatio(ratio) {
  if (ratio <= 0) return 0;
  if (ratio < 0.15) return 1;
  if (ratio < 0.4) return 2;
  if (ratio < 0.7) return 3;
  return 4;
}

function formatDate(dateStr) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}

function weekdayLabel(dateStr) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  return ["日", "月", "火", "水", "木", "金", "土"][d.getUTCDay()];
}

export default function CalendarHeatmap({ dates, topByDate, imageByName, surges, today, onDateClick }) {
  const maxScore = Math.max(1, ...dates.map((d) => topByDate[d]?.[0]?.score ?? 0));

  return (
    <div>
      <div className="calendar-strip">
        {dates.map((date) => {
          const top = topByDate[date] ?? [];
          const score = top[0]?.score ?? 0;
          const ratio = score / maxScore;
          const level = levelForRatio(ratio);
          const isToday = date === today;
          const isFuture = date > today;
          const surging = new Set(surges?.[date] ?? []);
          return (
            <button
              key={date}
              type="button"
              className={`calendar-cell${isToday ? " calendar-cell-today" : ""}${
                isFuture ? " calendar-cell-future" : ""
              }`}
              style={{ backgroundColor: LEVEL_COLORS[level] }}
              title={top.map((t) => `${t.pokemon_name} (${t.score.toFixed(1)})`).join(", ") || date}
              onClick={() => onDateClick?.(date)}
            >
              <div className="calendar-cell-weekday">{weekdayLabel(date)}</div>
              <div className="calendar-cell-date">{formatDate(date)}</div>
              <div className="calendar-cell-icons">
                {top.map((t) => (
                  <span key={t.pokemon_name} className="calendar-cell-icon-wrap">
                    {imageByName[t.pokemon_name] ? (
                      <img
                        className="calendar-cell-icon"
                        src={imageByName[t.pokemon_name]}
                        alt={t.pokemon_name}
                      />
                    ) : (
                      <span className="calendar-cell-icon calendar-cell-icon-placeholder" />
                    )}
                    {surging.has(t.pokemon_name) && (
                      <span className="calendar-cell-surge" title="急上昇中">
                        ▲
                      </span>
                    )}
                  </span>
                ))}
              </div>
              {isToday && <div className="calendar-cell-tag calendar-cell-tag-today">きょう</div>}
              {isFuture && <div className="calendar-cell-tag calendar-cell-tag-forecast">よそう</div>}
            </button>
          );
        })}
      </div>
      <div className="calendar-legend">
        <span>使用率の勢い:</span>
        {LEVEL_COLORS.map((color, i) => (
          <span key={i} className="calendar-legend-swatch" style={{ backgroundColor: color }} />
        ))}
        <span>低 → 高</span>
        <span className="calendar-legend-surge">
          <span className="calendar-cell-surge calendar-legend-surge-mark">▲</span> = 急上昇中
        </span>
      </div>
    </div>
  );
}
