from algotrader.meta_controller import MetaController
from algotrader.risk_gate import RiskGate
from algotrader.state import StateStore
from algotrader.domain import Signal


def test_state_store_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(str(path))
    store.save({"weights": {"decision": 0.6, "analytical": 0.4}})
    assert store.load()["weights"]["decision"] == 0.6


def test_meta_and_gate_survive_reload(tmp_path):
    meta = MetaController(engine_names=["decision", "analytical"])
    meta.update_weights({"decision": (Signal.LONG, 1.0), "analytical": (Signal.HOLD, 0.0)}, Signal.LONG)
    gate = RiskGate()
    gate.start_session(1000.0)
    gate.record_trade_result(-60.0)
    store = StateStore(str(tmp_path / "s.json"))
    store.save({"weights": meta.weights, "risk_gate": gate.snapshot_state()})
    meta2 = MetaController(engine_names=["decision", "analytical"])
    gate2 = RiskGate()
    payload = store.load()
    meta2.load_weights(payload["weights"])
    gate2.load_state(payload["risk_gate"])
    assert meta2.weights["decision"] > meta2.weights["analytical"]
    assert gate2.allow(940.0, 1.0, 100.0)[0] is False
