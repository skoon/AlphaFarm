from game.camera import Camera
from game.config import load_config


def make_cam():
    cfg = load_config()
    # 40x30 map at ts=32 -> 1280x960 world px; window equals map size here
    return Camera(cfg, 1280, 960, 1280, 960)


def test_view_is_window_over_zoom():
    cam = make_cam()
    assert cam.zoom == 2
    assert (cam.view_w, cam.view_h) == (640, 480)


def test_center_on_clamps_to_map_bounds():
    cam = make_cam()
    cam.center_on(0, 0)
    assert (cam.x, cam.y) == (0.0, 0.0)
    cam.center_on(1280, 960)
    assert (cam.x, cam.y) == (640.0, 480.0)
    cam.center_on(640, 480)
    assert (cam.x, cam.y) == (320.0, 240.0)


def test_update_eases_toward_target_and_converges():
    cam = make_cam()
    cam.center_on(0, 0)
    for _ in range(300):
        cam.update(1 / 60, 640, 480)
    assert abs(cam.x - 320) < 1 and abs(cam.y - 240) < 1


def test_visible_tiles_covers_view_with_margin():
    cam = make_cam()
    cam.center_on(640, 480)
    x0, y0, x1, y1 = cam.visible_tiles(32)
    assert x0 <= 320 // 32 and y0 <= 240 // 32
    assert x1 >= (320 + 640) // 32 and y1 >= (240 + 480) // 32


def test_world_to_screen_round_trip():
    cam = make_cam()
    cam.center_on(640, 480)
    sx, sy = cam.world_to_screen(640, 480)
    # camera centered on this point -> it lands at the window center
    assert (sx, sy) == (640, 480)
