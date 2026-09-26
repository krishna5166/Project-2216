from algotrader.meta_controller import MetaController, Signal


def test_equal_weights_at_start():
    meta = MetaController(engine_names=["a", "b"])
    assert meta.weights == {"a": 0.5, "b": 0.5}


def test_combine_agrees_goes_long():
    meta = MetaController(engine_names=["a", "b"])
    votes = {"a": (Signal.LONG, 1.0), "b": (Signal.LONG, 1.0)}
    assert meta.combine(votes) is Signal.LONG


def test_combine_disagreement_holds():
    meta = MetaController(engine_names=["a", "b"])
    votes = {"a": (Signal.LONG, 1.0), "b": (Signal.SHORT, 1.0)}
    assert meta.combine(votes) is Signal.HOLD


def test_winning_engine_gains_weight_over_time():
    meta = MetaController(engine_names=["good", "bad"])
    votes = {"good": (Signal.LONG, 1.0), "bad": (Signal.SHORT, 1.0)}

    for _ in range(10):
        meta.update_weights(votes, trade_direction=Signal.LONG)

    assert meta.weights["good"] > meta.weights["bad"]


def test_abstaining_engine_weight_unchanged_relative_reward():
    meta = MetaController(engine_names=["active", "abstainer"])
    votes = {"active": (Signal.LONG, 1.0), "abstainer": (Signal.HOLD, 0.0)}

    before = meta.weights["abstainer"]
    meta.update_weights(votes, trade_direction=Signal.LONG)
    # abstainer's raw weight is untouched, but normalization still shifts its
    # share since the active engine's weight grew
    assert meta.weights["abstainer"] <= before
