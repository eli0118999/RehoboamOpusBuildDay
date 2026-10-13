import json

from rehoboam import llm, state
from rehoboam.plain import _collect, plainify


def _restore():
    llm._run_dir, llm._replay, llm._fill_missing = None, False, False


def test_plainify_fills_from_recording_and_skips_known(tmp_path):
    st = state.load_state("sample", 0)
    originals = list(_collect(st))
    (tmp_path / "calls").mkdir()
    items = [{"id": f"h{i + 1}", "plain": f"plain {i}", "explain": f"explain {i}"} for i in range(len(originals))]
    (tmp_path / "calls" / "plain__t00.json").write_text(json.dumps({"output": {"items": items}}), encoding="utf-8")
    try:
        llm.configure(tmp_path, replay=True)
        assert plainify(st) == len(originals)
        first = originals[0]
        assert st.plain[first].plain == "plain 0"
        # everything known now: no second call (would raise MissingRecording for an absent key)
        st.tick = 99
        assert plainify(st) == 0
    finally:
        _restore()


def test_collect_covers_headlines_prior_paths_and_death():
    st = state.load_state("sample", 2)
    keys = _collect(st)
    rs = next(s for s in st.resident_states if s.prior_paths)
    assert rs.prior_paths[0][0].headline in keys
    assert rs.prediction.death_forecast.cause in keys
