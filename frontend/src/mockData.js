// Sample data for local development before a real Supabase project/backend
// pipeline is set up. Enabled via VITE_USE_MOCK_DATA=true (see .env.example).
export function generateMockRows() {
  const names = ["ピカチュウ", "カイリュー", "ルカリオ", "ゲンガー"];
  const rows = [];
  for (let i = -5; i <= 3; i++) {
    const dt = new Date();
    dt.setDate(dt.getDate() + i);
    const date = dt.toISOString().slice(0, 10);
    for (const name of names) {
      const base = (5 - Math.abs(i)) * 150;
      rows.push({ date, pokemon_name: name, score: Math.max(0, base + Math.random() * 150) });
    }
  }
  return rows;
}
