import io

from PIL import Image, ImageDraw

import imagehash

from aliasgraph.scraping.avatar import hamming_similarity


def _phash_of(img: Image.Image) -> str:
    return str(imagehash.phash(img))


def test_identical_images_score_one():
    img = Image.new("RGB", (64, 64), color=(120, 50, 200))
    h = _phash_of(img)
    assert hamming_similarity(h, h) == 1.0


def test_similar_images_score_high():
    img_a = Image.new("RGB", (64, 64), color=(120, 50, 200))
    # Same shape, slightly tinted
    img_b = Image.new("RGB", (64, 64), color=(125, 55, 205))
    sim = hamming_similarity(_phash_of(img_a), _phash_of(img_b))
    assert sim >= 0.95


def test_different_images_score_low():
    img_a = Image.new("RGB", (64, 64), color=(255, 0, 0))
    img_b = Image.new("RGB", (64, 64), color=(0, 255, 0))
    draw_b = ImageDraw.Draw(img_b)
    draw_b.rectangle([10, 10, 50, 50], fill=(0, 0, 0))
    sim = hamming_similarity(_phash_of(img_a), _phash_of(img_b))
    assert sim < 0.85


def test_none_inputs_yield_zero():
    assert hamming_similarity(None, None) == 0.0
    assert hamming_similarity("abc", None) == 0.0


def test_invalid_hash_returns_zero():
    assert hamming_similarity("not-a-hash", "also-not") == 0.0


def test_image_round_trip_io():
    img = Image.new("RGB", (32, 32), color=(10, 200, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    with Image.open(buf) as decoded:
        decoded.load()
        h = _phash_of(decoded)
    assert hamming_similarity(h, _phash_of(img)) == 1.0
