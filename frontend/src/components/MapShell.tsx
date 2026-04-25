export function MapShell() {
  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">Lumen</p>
        <h1>Renewable cost surfaces for real siting decisions.</h1>
        <p className="body-copy">
          This scaffold is ready for Deck.gl, MapLibre, scenario controls, and
          site diagnostics. The backend API contract is in place so we can wire
          live scoring next.
        </p>
      </section>
      <section className="map-panel">
        <div className="map-placeholder">Map layer placeholder</div>
      </section>
    </main>
  );
}
