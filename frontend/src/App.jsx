import { useEffect, useMemo, useState } from "react";
import CalendarHeatmap from "./CalendarHeatmap";
import TopThree from "./TopThree";
import ContributionModal from "./ContributionModal";
import { generateMockRows, generateMockImages, generateMockContributions } from "./mockData";
import "./App.css";

const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === "true";
const SNAPSHOT_URL = import.meta.env.VITE_SNAPSHOT_URL;

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function App() {
  const [rows, setRows] = useState([]);
  const [imageByName, setImageByName] = useState({});
  const [contributions, setContributions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [modal, setModal] = useState(null); // { date, pokemonName? } | null

  useEffect(() => {
    if (USE_MOCK_DATA) {
      setRows(generateMockRows());
      setImageByName(generateMockImages());
      setContributions(generateMockContributions());
      setLoading(false);
      return;
    }

    let cancelled = false;

    fetch(SNAPSHOT_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`snapshot fetch failed: ${res.status}`);
        return res.json();
      })
      .then((snapshot) => {
        if (cancelled) return;
        setRows(snapshot.forecast ?? []);
        setImageByName(snapshot.images ?? {});
        setContributions(snapshot.contributions ?? []);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const dates = useMemo(() => [...new Set(rows.map((r) => r.date))].sort(), [rows]);

  const today = todayIso();

  const top3 = useMemo(() => {
    const totals = new Map();
    for (const row of rows) {
      if (row.date === today) {
        totals.set(row.pokemon_name, row.score);
      }
    }
    return [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
  }, [rows, today]);

  // Top 3 pokemon per date, shown as icons in each calendar day cell.
  const topByDate = useMemo(() => {
    const byDate = new Map();
    for (const row of rows) {
      if (!byDate.has(row.date)) byDate.set(row.date, []);
      byDate.get(row.date).push(row);
    }
    const map = {};
    for (const [date, dateRows] of byDate) {
      map[date] = dateRows
        .sort((a, b) => b.score - a.score)
        .slice(0, 3)
        .map((r) => ({ pokemon_name: r.pokemon_name, score: r.score }));
    }
    return map;
  }, [rows]);

  function openContributions(date, pokemonName = null) {
    setModal({ date, pokemonName });
  }

  const modalVideos = useMemo(() => {
    if (!modal) return [];
    return contributions
      .filter((c) => c.date === modal.date && (!modal.pokemonName || c.pokemon_name === modal.pokemonName))
      .sort((a, b) => b.contribution_score - a.contribution_score)
      .slice(0, 30);
  }, [contributions, modal]);

  return (
    <div className="app">
      <header>
        <h1>ポケモンチャンピオンズ 使用率予想カレンダー</h1>
        <p className="subtitle">
          YouTube上の実況動画の再生数・投稿からの経過時間・チャンネル登録者数から、
          各ポケモンが「今どれくらい模倣されて使われやすいか」を推定した勢いです。
          未来日は既知動画の減衰の見込みであり、新規投稿までは予測できません。
        </p>
      </header>

      {loading && <p>読み込み中...</p>}
      {error && <p className="error">読み込みエラー: {error}</p>}

      {!loading && !error && rows.length === 0 && (
        <p>まだデータがありません。バックエンドの収集ジョブが実行されるとここに表示されます。</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <>
          <TopThree
            top3={top3}
            imageByName={imageByName}
            onSelect={(name) => openContributions(today, name)}
          />

          <CalendarHeatmap
            dates={dates}
            topByDate={topByDate}
            imageByName={imageByName}
            today={today}
            onDateClick={openContributions}
          />
          <p className="calendar-hint">日付をタップすると、その日に影響した動画を確認できます。</p>
        </>
      )}

      {modal && (
        <ContributionModal
          date={modal.date}
          pokemonName={modal.pokemonName}
          videos={modalVideos}
          loading={false}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

export default App;
