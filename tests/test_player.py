from game.player import Player
from tests.helpers import make_cfg, make_world


def make_player(world=None, cfg=None):
    cfg = cfg or make_cfg()
    world = world or make_world(cfg)
    return Player(cfg, world.player_start), world


def test_player_moves_with_delta_time():
    player, world = make_player()
    x0 = player.x
    player.move(1, 0, 0.5, world)
    assert abs((player.x - x0) - player.speed * 0.5) < 1e-6


def test_no_diagonal_movement():
    player, world = make_player()
    x0, y0 = player.x, player.y
    player.move(1, 1, 0.1, world)
    assert player.y == y0  # vertical input dropped, 4-direction only
    assert player.x > x0


def test_collision_blocks_solid_tiles():
    player, world = make_player()
    # player starts just south of the habitat door; the wall beside it is solid
    for _ in range(100):
        player.move(0, -1, 0.05, world)
    # door tile is walkable but the wall row above it is not; player never enters a solid tile
    assert not world.is_solid(int(player.x), int(player.y))


def test_facing_and_target_tile():
    player, world = make_player()
    player.move(0, 1, 0.001, world)
    tx, ty = player.target_tile()
    assert (tx, ty) == (int(player.x), int(player.y) + 1)
    player.move(-1, 0, 0.001, world)
    tx, ty = player.target_tile()
    assert tx == int(player.x) - 1


def test_energy_spend_and_floor():
    cfg = make_cfg()
    player, _ = make_player(cfg=cfg)
    player.spend_energy("hoe")
    assert player.energy == player.max_energy - cfg["energy_costs"]["hoe"]
    player.energy = 1.0
    assert not player.can_afford_energy("hoe")
    player.drain_energy(5.0)
    assert player.energy == 0.0


def test_rest_and_collapse():
    cfg = make_cfg()
    player, _ = make_player(cfg=cfg)
    player.energy = 3.0
    player.rest(collapsed=False)
    assert player.energy == player.max_energy
    player.rest(collapsed=True)
    assert player.energy == player.max_energy * cfg["player"]["collapse_wake_energy_fraction"]


def test_player_save_roundtrip():
    player, world = make_player()
    player.credits = 999
    player.tool = "scanner"
    player.selected_seed = "prism_pod"
    other, _ = make_player(world)
    other.from_dict(player.to_dict())
    assert other.credits == 999
    assert other.tool == "scanner"
    assert other.selected_seed == "prism_pod"
