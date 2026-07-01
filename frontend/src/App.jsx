import { useEffect, useMemo, useState } from "react";
import { supabase } from "./supabaseClient";
import CalendarHeatmap from "./CalendarHeatmap";
import TopThree from "./TopThree";
import ContributionModal from "./ContributionModal";
import { generateMockRows, generateMockImages, generateMockContributions } from "./mockData";
import "./App.css";

const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === "true";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function App() {
  const [rows, setRows] = useState([]);
  const [imageByName, setImageByName] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [modal, setModal] = useState(null); // { date, pokemonName } | null
  const [modalVideos, setModalVideos] = useState([]);
  const [modalLoading, setModalLoading] = useState(false);

  useEffect(() => {
    if (USE_MOCK_DATA) {
      setRows(generateMockRows());
      setImageByName(generateMockImages());
      setLoading(false);
      return;
    }

    let cancelled = false;

    Promise.all([
      supabase.from("pokemon_daily_forecast").select("date, pokemon_name, score").order("date", { ascending: true }),
      supabase.from("pokemon_images").select("pokemon_name, image_url"),
    ]).then(([forecastResult, imagesResult]) => {
      if (cancelled) return;
      if (forecastResult.error) {
        setError(forecastResult.error.message);
      } else {
        setRows(forecastResult.data ?? []);
      }
      if (!imagesResult.error) {
        const images = {};
        for (const row of imagesResult.data ?? []) {
          images[row.pokemon_name] = row.image_url;
        }
        setImageByName(images);
      }
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

  // Best (top-1) pokemon per date, shown as the calendar day's icon.
  const bestByDate = useMemo(() => {
    const map = {};
    for (const row of rows) {
      const current = map[row.date];
      if (!current || row.score > current.score) {
        map[row.date] = { pokemon_name: row.pokemon_name, score: row.score };
      }
    }
    return map;
  }, [rows]);

  async function openContributions(date, pokemonName) {
    if (!pokemonName) return;
    setModal({ date, pokemonName });
    setModalLoading(true);

    if (USE_MOCK_DATA) {
      setModalVideos(generateMockContributions(date, pokemonName));
      setModalLoading(false);
      return;
    }

    const { data, error } = await supabase
      .from("pokemon_video_contribution")
      .select("video_id, video_title, youtube_url, published_at, contribution_score")
      .eq("date", date)
      .eq("pokemon_name", pokemonName)
      .order("contribution_score", { ascending: false });

    setModalVideos(error ? [] : data ?? []);
    setModalLoading(false);
  }

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
            bestByDate={bestByDate}
            imageByName={imageByName}
            today={today}
            onDateClick={(date) => openContributions(date, bestByDate[date]?.pokemon_name)}
          />
          <p className="calendar-hint">日付をタップすると、その日のTOP1ポケモンに影響した動画を確認できます。</p>
        </>
      )}

      {modal && (
        <ContributionModal
          date={modal.date}
          pokemonName={modal.pokemonName}
          videos={modalVideos}
          loading={modalLoading}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

export default App;
