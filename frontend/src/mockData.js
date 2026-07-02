// Sample data for local development before a real Supabase project/backend
// pipeline is set up. Enabled via VITE_USE_MOCK_DATA=true (see .env.example).

const MOCK_POKEMON = [
  { name: "ピカチュウ", dexNumber: 25 },
  { name: "カイリュー", dexNumber: 149 },
  { name: "ルカリオ", dexNumber: 448 },
  { name: "ゲンガー", dexNumber: 94 },
];

export function generateMockRows() {
  const rows = [];
  // 30-day window ending tomorrow, matching forecaster.py's CALENDAR_TOTAL_DAYS.
  for (let i = -28; i <= 1; i++) {
    const dt = new Date();
    dt.setDate(dt.getDate() + i);
    const date = dt.toISOString().slice(0, 10);
    for (const { name } of MOCK_POKEMON) {
      const base = Math.max(0, 5 - Math.abs(i)) * 150;
      rows.push({ date, pokemon_name: name, score: Math.max(0, base + Math.random() * 150) });
    }
  }
  return rows;
}

export function generateMockImages() {
  const images = {};
  for (const { name, dexNumber } of MOCK_POKEMON) {
    images[name] =
      `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${dexNumber}.png`;
  }
  return images;
}

export function generateMockContributions(date) {
  return MOCK_POKEMON.slice(0, 3).map(({ name }, i) => ({
    video_id: `mock-${date}-${i}`,
    pokemon_name: name,
    video_title: `【${name}】ポケモンチャンピオンズ 実況 #${i + 1}`,
    youtube_url: "https://www.youtube.com/",
    published_at: `${date}T09:00:00Z`,
    contribution_score: Math.max(0, 500 - i * 120 + Math.random() * 50),
  }));
}
