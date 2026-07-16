from game.npcs import NPCManager
from tests.helpers import make_cfg


def make_mgr():
    return NPCManager(make_cfg())


def test_all_five_npcs_load():
    mgr = make_mgr()
    assert set(mgr.npcs) == {"sylla", "hux", "tinks", "care7", "juno"}


def test_schedule_waypoint_selection():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    assert sylla.current_waypoint(6.5)["hour"] == 6.0
    assert sylla.current_waypoint(10.0)["hour"] == 9.0
    assert sylla.current_waypoint(25.0)["hour"] == 20.0


def test_npc_walks_toward_waypoint():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    x0, y0 = sylla.x, sylla.y
    target = sylla.current_waypoint(9.0)
    d0 = abs(target["x"] - x0) + abs(target["y"] - y0)
    sylla.update(9.0, 1.0)
    d1 = abs(target["x"] - sylla.x) + abs(target["y"] - sylla.y)
    assert d1 < d0


def test_talk_awards_points_once_per_day():
    cfg = make_cfg()
    mgr = NPCManager(cfg)
    juno = mgr.npcs["juno"]
    line = juno.talk_line(mgr.dialogue, day=1)
    assert isinstance(line, str) and line
    assert juno.friendship == cfg["npcs"]["talk_points_per_day"]
    juno.talk_line(mgr.dialogue, day=1)
    assert juno.friendship == cfg["npcs"]["talk_points_per_day"]
    mgr.end_of_day()
    juno.talk_line(mgr.dialogue, day=2)
    assert juno.friendship == 2 * cfg["npcs"]["talk_points_per_day"]


def test_dialogue_changes_with_friendship_tier():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    assert sylla.tier() == "acquaintance"
    sylla.friendship = 350
    assert sylla.tier() == "friend"
    sylla.friendship = 800
    assert sylla.tier() == "confidant"
    line = sylla.talk_line(mgr.dialogue, day=1)
    assert line in mgr.dialogue["sylla"]["confidant"]


def test_gift_preferences():
    cfg = make_cfg()
    mgr = NPCManager(cfg)
    hux = mgr.npcs["hux"]
    assert hux.gift_reaction("crimson_tuber") == "loved"
    assert hux.gift_reaction("gravity_melon") == "liked"
    assert hux.gift_reaction("prism_pod") == "disliked"
    assert hux.gift_reaction("whisper_wheat") == "neutral"


def test_gift_awards_points_and_limits_per_day():
    cfg = make_cfg()
    mgr = NPCManager(cfg)
    hux = mgr.npcs["hux"]
    assert hux.receive_gift("crimson_tuber") == "loved"
    assert hux.friendship == cfg["npcs"]["gift_loved"]
    assert hux.receive_gift("crimson_tuber") == "already_today"
    assert hux.friendship == cfg["npcs"]["gift_loved"]
    mgr.end_of_day()
    assert hux.receive_gift("prism_pod") == "disliked"
    assert hux.friendship == cfg["npcs"]["gift_loved"] + cfg["npcs"]["gift_disliked"]


def test_every_npc_has_ten_dialogue_lines():
    mgr = make_mgr()
    for nid in mgr.npcs:
        total = sum(len(mgr.dialogue[nid][tier])
                    for tier in ("acquaintance", "friend", "confidant"))
        assert total >= 10, f"{nid} has only {total} lines"


def test_npc_near_and_save_roundtrip():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    assert mgr.npc_near(int(sylla.x), int(sylla.y)) is sylla
    assert mgr.npc_near(0, 0) is None
    sylla.friendship = 123
    mgr2 = make_mgr()
    mgr2.from_dict(mgr.to_dict())
    assert mgr2.npcs["sylla"].friendship == 123
