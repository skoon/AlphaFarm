from game.quest import QuestSystem


def make_q():
    return QuestSystem()


def test_questline_has_five_steps():
    q = make_q()
    assert len(q.steps) == 5
    assert q.current_step["id"] == "signal"
    assert not q.finished


def test_step_gated_until_harvest_milestone():
    q = make_q()
    assert q.try_trigger("terminal", 0, 0.5, False) is None
    q.total_harvests = 10
    step = q.try_trigger("terminal", 0, 0.5, False)
    assert step and step["id"] == "signal"
    assert q.current_step["id"] == "translation"


def test_wrong_trigger_does_not_fire():
    q = make_q()
    q.total_harvests = 10
    assert q.try_trigger("talk_sylla", 0, 0.5, False) is None
    assert q.current_step["id"] == "signal"


def test_codex_and_resonance_gates():
    q = make_q()
    q.total_harvests = 10
    q.try_trigger("terminal", 0, 0.5, False)

    assert q.try_trigger("talk_sylla", 4, 0.5, False) is None
    assert q.try_trigger("talk_sylla", 5, 0.5, False)["id"] == "translation"

    assert q.try_trigger("terminal", 5, 0.6, False) is None
    assert q.try_trigger("terminal", 5, 0.66, False)["id"] == "resonance"


def test_final_step_requires_night():
    q = make_q()
    q.total_harvests = 25
    q.completed = ["signal", "translation", "resonance"]
    assert q.try_trigger("talk_care7", 9, 0.7, False)["id"] == "caretaker"
    assert q.try_trigger("great_crystal_night", 9, 0.7, False) is None
    final = q.try_trigger("great_crystal_night", 9, 0.7, True)
    assert final["id"] == "awakening"
    assert final["reward_seed"] == "dream_lotus"
    assert q.finished


def test_hint_reflects_progress():
    q = make_q()
    assert "harvests" in q.hint(0, 0.5)
    q.total_harvests = 10
    assert "terminal" in q.hint(0, 0.5).lower()


def test_quest_save_roundtrip():
    q = make_q()
    q.total_harvests = 12
    q.completed = ["signal"]
    q2 = make_q()
    q2.from_dict(q.to_dict())
    assert q2.total_harvests == 12
    assert q2.current_step["id"] == "translation"
    assert len(q2.journal_entries()) == 1
