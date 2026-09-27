from types import SimpleNamespace

from skincare_dupe_bot import config
from skincare_dupe_bot.video.image_builder import build_scene_images, render_card
from skincare_dupe_bot.video.script_writer import generate_script


def test_render_card_produces_correct_size():
    img = render_card("hook", eyebrow="Dupe alert", headline="Test headline")
    assert img.size == (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
    assert img.mode == "RGB"


def test_build_scene_images_returns_four_scenes():
    kb = SimpleNamespace(brand="TestKB", name="Test Essence", category="essence", typical_price_usd=25.0)
    dupe = SimpleNamespace(
        brand="TestDupe", name="Test Cream", category="moisturizer", key_actives="niacinamide",
        match_notes="shares niacinamide", retailer="cvs", last_known_price_usd=10.0, typical_price_usd=10.0,
    )
    script = generate_script(kb, dupe)
    scenes = build_scene_images(kb, dupe, script)

    assert len(scenes) == 4
    for img in scenes:
        assert img.size == (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
