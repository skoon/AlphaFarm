from game.npcs import NPCManager, find_path, line_matches, location_zone
from tests.helpers import make_cfg, make_world


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
    world = make_world()
    sylla = mgr.npcs["sylla"]
    x0, y0 = sylla.x, sylla.y
    target = sylla.current_waypoint(9.0)
    d0 = abs(target["x"] - x0) + abs(target["y"] - y0)
    sylla.update(9.0, 1.0, world, storm=False)
    d1 = abs(target["x"] - sylla.x) + abs(target["y"] - sylla.y)
    assert d1 < d0


def test_npc_path_avoids_solid_tiles():
    mgr = make_mgr()
    world = make_world()
    sylla = mgr.npcs["sylla"]
    # walk the whole 9:00 commute (outpost -> mid-map) in small steps
    for _ in range(2000):
        sylla.update(9.0, 1 / 30, world, storm=False)
        assert not world.is_solid(round(sylla.x), round(sylla.y)), \
            f"sylla inside a solid tile at ({sylla.x:.1f},{sylla.y:.1f})"
    target = sylla.current_waypoint(9.0)
    assert (round(sylla.x), round(sylla.y)) == (target["x"], target["y"])


def test_npc_goes_indoors_at_night_and_storm_hides_at_home():
    cfg = make_cfg()
    mgr = NPCManager(cfg)
    world = make_world(cfg)
    hux = mgr.npcs["hux"]
    hux.x, hux.y = float(hux.home[0]), float(hux.home[1])
    hux.update(23.0, 1 / 60, world, storm=False)
    assert hux.hidden
    assert mgr.npc_near(hux.home[0], hux.home[1]) is None
    hux.hidden = False
    hux.update(12.0, 1 / 60, world, storm=True)
    assert hux.hidden  # sheltering at home during the storm


def test_dialogue_context_selector():
    mgr = make_mgr()
    world = make_world()
    dialogue = {
        "juno": {"acquaintance": [
            "generic one",
            "generic two",
            {"text": "storm line", "when": {"event": "ion_storm"}},
            {"text": "crystal line", "when": {"location": "crystal"}},
        ]}
    }
    juno = mgr.npcs["juno"]
    ctx = {"event": "ion_storm", "moons": set(), "location": "outpost", "quests": set()}
    assert juno.talk_line(dialogue, day=1, ctx=ctx) == "storm line"
    ctx = {"event": "none", "moons": set(), "location": "crystal", "quests": set()}
    assert juno.talk_line(dialogue, day=1, ctx=ctx) == "crystal line"
    ctx = {"event": "none", "moons": set(), "location": "outpost", "quests": set()}
    assert juno.talk_line(dialogue, day=1, ctx=ctx).startswith("generic")
    assert location_zone(world, 26, 12) == "crystal"
    assert location_zone(world, 33, 24) == "outpost"
    assert location_zone(world, 10, 12) == "farm"


def test_line_matches_conditions():
    ctx = {"event": "aurora", "moons": {"ilo:full"}, "location": "farm",
           "quests": {"signal"}}
    assert line_matches({"text": "x", "when": {"event": "aurora"}}, ctx)
    assert line_matches({"text": "x", "when": {"moon": "ilo:full",
                                               "min_quest": "signal"}}, ctx)
    assert not line_matches({"text": "x", "when": {"moon": "vesk:full"}}, ctx)
    assert not line_matches("plain string", ctx)


def test_heart_event_fires_once_and_awards_bonus():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    events = {"sylla": [{"id": "sylla_3", "hearts": 3, "bonus": 50, "pages": ["a", "b"]}]}
    assert sylla.pending_heart_event(events) is None
    sylla.friendship = 300  # 3 hearts
    ev = sylla.pending_heart_event(events)
    assert ev and ev["id"] == "sylla_3"
    sylla.complete_heart_event(ev)
    assert sylla.friendship == 350
    assert sylla.pending_heart_event(events) is None
    mgr2 = make_mgr()
    mgr2.from_dict(mgr.to_dict())
    assert mgr2.npcs["sylla"].pending_heart_event(events) is None


def test_perk_thresholds():
    cfg = make_cfg()
    mgr = NPCManager(cfg)
    assert not mgr.perk("tinks")
    mgr.npcs["tinks"].friendship = cfg["npcs"]["perk_thresholds"]["tinks"]
    assert mgr.perk("tinks")
    assert not mgr.perk("care7")


def test_find_path_routes_around_obstacles():
    world = make_world()
    # habitat dome at (2,2)-(4,6) is solid; path from its left to its right must detour
    path = find_path(world, (1, 4), (6, 4))
    assert path is not None
    assert path[-1] == (6, 4)
    for step in path:
        assert not world.is_solid(*step)


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


def test_every_npc_sprite_file_exists():
    from game.config import BASE_DIR
    mgr = make_mgr()
    for nid, npc in mgr.npcs.items():
        sprite = npc.d.get("sprite")
        assert sprite, f"{nid} has no sprite assigned"
        assert (BASE_DIR / "assets" / sprite).exists(), f"{nid}: missing {sprite}"


def test_npc_near_and_save_roundtrip():
    mgr = make_mgr()
    sylla = mgr.npcs["sylla"]
    assert mgr.npc_near(int(sylla.x), int(sylla.y)) is sylla
    assert mgr.npc_near(0, 0) is None
    sylla.friendship = 123
    mgr2 = make_mgr()
    mgr2.from_dict(mgr.to_dict())
    assert mgr2.npcs["sylla"].friendship == 123
