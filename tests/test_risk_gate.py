from algotrader.risk_gate import RiskGate


def test_allows_reasonable_order():
    gate = RiskGate()
    gate.start_session(equity=1000.0)
    allowed, reason = gate.allow(equity=1000.0, qty=1.0, price=100.0)
    assert allowed is True
    assert reason is None


def test_blocks_oversized_position():
    gate = RiskGate(max_position_fraction=0.25)
    gate.start_session(equity=1000.0)
    # 1000 qty * 100 price = way over 25% of 1000 equity
    allowed, reason = gate.allow(equity=1000.0, qty=10.0, price=100.0)
    assert allowed is False
    assert "exceeds max allowed" in reason


def test_trips_after_daily_loss_limit_breached():
    gate = RiskGate(max_daily_loss_fraction=0.05)
    gate.start_session(equity=1000.0)
    gate.record_trade_result(-60.0)  # exceeds 5% of 1000 = -50
    allowed, reason = gate.allow(equity=940.0, qty=1.0, price=100.0)
    assert allowed is False
    assert "Daily loss limit" in reason


def test_manual_kill_switch_blocks_orders(monkeypatch):
    gate = RiskGate()
    gate.start_session(equity=1000.0)
    monkeypatch.setenv("KILL_SWITCH", "true")
    allowed, reason = gate.allow(equity=1000.0, qty=1.0, price=100.0)
    assert allowed is False
    assert "kill switch" in reason.lower()


def test_start_session_resets_trip_state():
    gate = RiskGate(max_daily_loss_fraction=0.05)
    gate.start_session(equity=1000.0)
    gate.record_trade_result(-60.0)
    assert gate.allow(equity=940.0, qty=1.0, price=100.0)[0] is False

    gate.start_session(equity=940.0)
    assert gate.allow(equity=940.0, qty=1.0, price=100.0)[0] is True
