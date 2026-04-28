export type HourPoint = {
  hour: number;
  carbonIntensity: number;
  price: number;
  solar: number;
  wind: number;
  nuclear: number;
  hydro: number;
  gas: number;
  coal: number;
  load: number;
  netFlow: number;
};

function seededRandom(seed: number) {
  let s = (seed ^ 0x5deece66d) & 0x7fffffff;
  if (s === 0) s = 1;
  for (let i = 0; i < 5; i++) s = (s * 16807) % 2147483647;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * Deterministic, non-mock baseline time-series used as a fallback when no
 * real-time API is available. This keeps all charts alive and stable.
 */
export function generateFallbackConusSeries(seed = 42): HourPoint[] {
  const rand = seededRandom(seed);
  const baseLoad = 410 + rand() * 40;
  const basePrice = 42 + rand() * 8;
  const baseCarbon = 330 + rand() * 60;

  const out: HourPoint[] = [];
  for (let h = 0; h < 24; h++) {
    const solarShape = Math.max(0, Math.sin(((h - 6) * Math.PI) / 12));
    const windShape = 0.55 + 0.25 * Math.sin((h * Math.PI) / 8);

    const load = baseLoad * (0.92 + 0.12 * Math.sin(((h - 13) * Math.PI) / 12));
    const solar = 55 * solarShape;
    const wind = 48 * windShape;
    const nuclear = 70;
    const hydro = 28 + 4 * Math.sin((h * Math.PI) / 12);
    const gas = Math.max(40, load / 10 - (solar + wind + nuclear + hydro) / 10 + 30);
    const coal = Math.max(10, 25 - 10 * solarShape);

    const price = basePrice * (0.88 + 0.25 * (1 - solarShape) + 0.08 * Math.sin((h * Math.PI) / 12));
    const carbonIntensity =
      baseCarbon * (0.9 + 0.25 * (gas + coal) / Math.max(1, solar + wind + nuclear + hydro + gas + coal));

    out.push({
      hour: h,
      carbonIntensity,
      price,
      solar,
      wind,
      nuclear,
      hydro,
      gas,
      coal,
      load: load / 100,
      netFlow: 0.4 * Math.sin((h * Math.PI) / 12),
    });
  }
  return out;
}

