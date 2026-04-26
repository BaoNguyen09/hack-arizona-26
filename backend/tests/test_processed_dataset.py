from pathlib import Path

from backend.app.data.processed_dataset import DATASET_COLUMNS, ProcessedCellRecord, load_processed_cell_records


def test_processed_dataset_fixture_has_required_shape() -> None:
    dataset_path = Path("data/processed/lumen_cells.csv")
    records = load_processed_cell_records(dataset_path)

    assert dataset_path.exists()
    header = dataset_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == DATASET_COLUMNS
    assert len(records) >= 25
    assert len({record.cell_id for record in records}) == len(records)
    assert len({record.region for record in records}) >= 8


def test_processed_dataset_loader_returns_typed_records() -> None:
    records = load_processed_cell_records()

    assert records
    assert all(isinstance(record, ProcessedCellRecord) for record in records)
    assert all(0.0 <= record.solar_cf <= 1.0 for record in records)
    assert all(0.0 <= record.wind_cf <= 1.0 for record in records)
    assert all(record.avg_price_per_mwh >= 0.0 for record in records)
    assert all(record.carbon_intensity_g_per_kwh >= 0.0 for record in records)
    assert all(record.nearest_transmission_km >= 0.0 for record in records)
