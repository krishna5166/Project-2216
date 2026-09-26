from algotrader.recorder import TickRecorder, load_ticks


def test_record_and_load_roundtrip(tmp_path):
    path = tmp_path / "ticks.jsonl"
    recorder = TickRecorder(str(path))
    for price in [100.0, 100.5, 101.2]:
        recorder.record(price)
    recorder.close()

    prices = list(load_ticks(str(path)))
    assert prices == [100.0, 100.5, 101.2]


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "ticks.jsonl"
    recorder = TickRecorder(str(path))
    recorder.record(50.0)
    recorder.close()

    assert path.exists()
    assert list(load_ticks(str(path))) == [50.0]
