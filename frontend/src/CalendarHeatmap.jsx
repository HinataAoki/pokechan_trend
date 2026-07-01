const LEVEL_COLORS = ["#eef7ee", "#c8ecc0", "#f7e28a", "#f2a154", "#e2543a"];

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

export default function CalendarHeatmap({ dates, scoreByDate, today, onDateClick }) {
  const maxScore = Math.max(1, ...Object.values(scoreByDate));

  return (
    <div>
      <div className="calendar-strip">
        {dates.map((date) => {
          const score = scoreByDate[date] ?? 0;
          const ratio = score / maxScore;
          const level = levelForRatio(ratio);
          const isToday = date === today;
          const isFuture = date > today;
          return (
            <button
              key={date}
              type="button"
              className={`calendar-cell${isToday ? " calendar-cell-today" : ""}`}
              style={{ backgroundColor: LEVEL_COLORS[level] }}
              title={`${date}: score ${score.toFixed(1)}`}
              onClick={() => onDateClick?.(date)}
            >
              <div className="calendar-cell-weekday">{weekdayLabel(date)}</div>
              <div className="calendar-cell-date">{formatDate(date)}</div>
              <div className="calendar-cell-score">{score > 0 ? score.toFixed(0) : "-"}</div>
              {isFuture && <div className="calendar-cell-forecast-tag">予想</div>}
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
      </div>
    </div>
  );
}
