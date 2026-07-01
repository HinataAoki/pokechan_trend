import { useEffect, useMemo, useState } from "react";
import { supabase } from "./supabaseClient";
import CalendarHeatmap from "./CalendarHeatmap";
import { generateMockRows } from "./mockData";
import "./App.css";

const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === "true";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function App() {
  const [rows, setRows] = useState([]);
  const [selectedPokemon, setSelectedPokemon] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (USE_MOCK_DATA) {
      setRows(generateMockRows());
      setLoading(false);
      return;
    }

    let cancelled = false;

    supabase
      .from("pokemon_daily_forecast")
      .select("date, pokemon_name, score")
      .order("date", { ascending: true })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error) {
          setError(error.message);
        } else {
          setRows(data ?? []);
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

  const scoreByDate = useMemo(() => {
    const map = {};
    for (const row of rows) {
      if (row.pokemon_name === selectedPokemon) {
        map[row.date] = row.score;
      }
    }
    return map;
  }, [rows, selectedPokemon]);

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
          <div className="pokemon-select">
            <label htmlFor="pokemon">ポケモン: </label>
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

          <CalendarHeatmap dates={dates} scoreByDate={scoreByDate} today={todayIso()} />
        </>
      )}
    </div>
  );
}

export default App;
