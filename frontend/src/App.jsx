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
  const [selectedPokemon, setSelectedPokemon] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [modalDate, setModalDate] = useState(null);
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

  const pokemonTotals = useMemo(() => {
    const totals = new Map();
    for (const row of rows) {
      totals.set(row.pokemon_name, (totals.get(row.pokemon_name) ?? 0) + row.score);
    }
    return [...totals.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  useEffect(() => {
    if (!selectedPokemon && pokemonTotals.length > 0) {
      setSelectedPokemon(pokemonTotals[0][0]);
    }
  }, [pokemonTotals, selectedPokemon]);

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

  const scoreByDate = useMemo(() => {
    const map = {};
    for (const row of rows) {
      if (row.pokemon_name === selectedPokemon) {
        map[row.date] = row.score;
      }
    }
    return map;
  }, [rows, selectedPokemon]);

  async function handleDateClick(date) {
    setModalDate(date);
    setModalLoading(true);

    if (USE_MOCK_DATA) {
      setModalVideos(generateMockContributions(date, selectedPokemon));
      setModalLoading(false);
      return;
    }

    const { data, error } = await supabase
      .from("pokemon_video_contribution")
      .select("video_id, video_title, youtube_url, published_at, contribution_score")
      .eq("date", date)
      .eq("pokemon_name", selectedPokemon)
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
          <TopThree top3={top3} imageByName={imageByName} onSelect={setSelectedPokemon} />

          <div className="pokemon-select">
            <label htmlFor="pokemon">ポケモン: </label>
            {imageByName[selectedPokemon] && (
              <img className="pokemon-select-icon" src={imageByName[selectedPokemon]} alt="" />
            )}
            <select
              id="pokemon"
              value={selectedPokemon}
              onChange={(e) => setSelectedPokemon(e.target.value)}
            >
              {pokemonTotals.map(([name]) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <CalendarHeatmap
            dates={dates}
            scoreByDate={scoreByDate}
            today={today}
            onDateClick={handleDateClick}
          />
          <p className="calendar-hint">日付をタップすると、その日に影響した動画を確認できます。</p>
        </>
      )}

      {modalDate && (
        <ContributionModal
          date={modalDate}
          pokemonName={selectedPokemon}
          videos={modalVideos}
          loading={modalLoading}
          onClose={() => setModalDate(null)}
        />
      )}
    </div>
  );
}

export default App;
