from algotrader.meta_controller import MetaController
from algotrader.domain import Signal


def test_equal_weights_at_start():
    meta = MetaController(engine_names=["a", "b"])
    assert meta.weights == {"a": 0.5, "b": 0.5}


def test_combine_agrees_goes_long():
    meta = MetaController(engine_names=["a", "b"])
    assert meta.combine({"a": (Signal.LONG, 1.0), "b": (Signal.LONG, 1.0)}) is Signal.LONG


def test_combine_disagreement_holds():
    meta = MetaController(engine_names=["a", "b"])
    assert meta.combine({"a": (Signal.LONG, 1.0), "b": (Signal.SHORT, 1.0)}) is Signal.HOLD


def test_winning_engine_gains_weight_over_time():
    meta = MetaController(engine_names=["good", "bad"])
    votes = {"good": (Signal.LONG, 1.0), "bad": (Signal.SHORT, 1.0)}
    for _ in range(10):
        meta.update_weights(votes, trade_direction=Signal.LONG)
    assert meta.weights["good"] > meta.weights["bad"]


def test_abstaining_engine_weight_unchanged_relative_reward():
    meta = MetaController(engine_names=["active", "abstainer"])
    before = meta.weights["abstainer"]
    meta.update_weights({"active": (Signal.LONG, 1.0), "abstainer": (Signal.HOLD, 0.0)}, Signal.LONG)
    assert meta.weights["abstainer"] <= before
