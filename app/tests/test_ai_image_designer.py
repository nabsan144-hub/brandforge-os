"""AI image design engine — brand briefs, provider transports, compositing.

All network calls are mocked: these tests verify request shape, response
parsing, fallback chains and the offline promise without any key or network.
"""

import base64
import json
import os
import struct
import sys
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ai_image_designer import (
    AIImageDesigner,
    IMAGE_PROVIDERS,
    build_design_brief,
    _b64_image,
    _valid_image_bytes,
)
from modules.visual_designer import VisualDesigner


# ---------------------------------------------------------------- helpers

def tiny_png(w=60, h=40, rgb=(180, 70, 30)):
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    rows = b""
    for _ in range(h):
        rows += b"\x00" + bytes(rgb) * w
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


B64_PNG = base64.b64encode(tiny_png()).decode()


def make_engine(tmp_path, env=None, config=None):
    """Standalone designer over a temp base dir with injected .env/config."""
    env = env or {}
    config = config or {}
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
    (tmp_path / "config.json").write_text(json.dumps(config))
    return AIImageDesigner(base_dir=str(tmp_path))


# ---------------------------------------------------------------- brief

def test_design_brief_carries_brand_context():
    brief = build_design_brief(
        "Sindh Ceramics", "Handmade Tiles", "Interior Architects",
        ["40-year lifespan", "Hand-glazed craft"],
        "#C2410C", "#1C1917", 1200, 630,
    )
    assert "Sindh Ceramics" in brief
    assert "#C2410C" in brief and "#1C1917" in brief
    assert "Interior Architects" in brief
    assert "no text" in brief and "no watermarks" in brief
    # composition guidance depends on aspect bucket
    assert "left half" in brief  # wide -> typography space on the left


def test_design_brief_square_composition():
    brief = build_design_brief("Brand", "Retail", "Shoppers", None, "#AABBCC", "#112233", 1080, 1080)
    assert "square" in brief
    assert "top and bottom" in brief


# ---------------------------------------------------------------- validation

def test_valid_image_bytes_rejects_garbage():
    assert _valid_image_bytes(tiny_png()) is not None
    assert _valid_image_bytes(b"not an image at all........") is None
    assert _valid_image_bytes(b"") is None
    assert _valid_image_bytes(None) is None
    # A signature alone is not proof of a decodable image
    assert _valid_image_bytes(b"\xff\xd8\xff" + b"x" * 200) is None
    # b64 path decodes or rejects
    assert _b64_image(B64_PNG) is not None
    assert _b64_image("!!!not-base64!!!") is None


# ---------------------------------------------------------------- gemini transport

def test_gemini_happy_path_and_request_shape():
    from modules.ai_image_designer import _gemini_generate
    response = mock.Mock(status_code=200)
    response.json.return_value = {
        "candidates": [{"content": {"parts": [
            {"text": "here is your image"},
            {"inlineData": {"mimeType": "image/png", "data": B64_PNG}},
        ]}}]
    }
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response) as post:
        data = _gemini_generate("prompt", "wide", "KEY1234567890", "gemini-3-pro-image-preview")
    assert data == tiny_png()
    url = post.call_args.args[0]
    body = json.loads(post.call_args.kwargs["data"])
    assert "gemini-3-pro-image-preview:generateContent" in url
    assert body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "KEY1234567890"


def test_gemini_text_only_response_returns_none():
    from modules.ai_image_designer import _gemini_generate
    response = mock.Mock(status_code=200)
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "no image for you"}]}}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response):
        assert _gemini_generate("p", "wide", "KEY1234567890", "m") is None


# ---------------------------------------------------------------- openai-compatible transport

def test_xai_b64_json_path():
    from modules.ai_image_designer import _openai_compatible_generate
    response = mock.Mock(status_code=200)
    response.json.return_value = {"data": [{"b64_json": B64_PNG}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response) as post:
        data = _openai_compatible_generate(
            "https://api.x.ai/v1/images/generations", "XKEY123456",
            "grok-imagine-image-2.0", "p", "wide", "xai",
        )
    assert data == tiny_png()
    body = json.loads(post.call_args.kwargs["data"])
    assert body["model"] == "grok-imagine-image-2.0"
    assert body["aspect_ratio"] == "16:9"
    assert body["response_format"] == "b64_json"


def test_openai_uses_size_and_never_response_format():
    from modules.ai_image_designer import _openai_compatible_generate
    response = mock.Mock(status_code=200)
    response.json.return_value = {"data": [{"b64_json": B64_PNG}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response) as post:
        data = _openai_compatible_generate(
            "https://api.openai.com/v1/images/generations", "OKEY123456",
            "gpt-image-1", "p", "square", "openai",
        )
    assert data == tiny_png()
    body = json.loads(post.call_args.kwargs["data"])
    assert body["size"] == "1024x1024"
    assert "response_format" not in body  # gpt-image-1 rejects it


def test_xai_url_fallback_fetches_https_only():
    from modules.ai_image_designer import _openai_compatible_generate
    response = mock.Mock(status_code=200)
    response.json.return_value = {"data": [{"url": "https://cdn.x.ai/img.jpg"}]}
    img_response = mock.Mock(status_code=200, content=tiny_png(60, 40))
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response), \
         mock.patch("modules.ai_image_designer.fetch_public", return_value=img_response) as get:
        data = _openai_compatible_generate(
            "https://api.x.ai/v1/images/generations", "XKEY123456",
            "grok-imagine-image-2.0", "p", "wide", "xai",
        )
    assert data is not None
    assert get.call_args.args[0].startswith("https://")
    # non-https URL is never fetched
    response.json.return_value = {"data": [{"url": "http://evil.example/x.jpg"}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response), \
         mock.patch("modules.ai_image_designer.requests.get") as get2:
        data2 = _openai_compatible_generate(
            "https://api.x.ai/v1/images/generations", "XKEY123456",
            "grok-imagine-image-2.0", "p", "wide", "xai",
        )
    assert data2 is None
    get2.assert_not_called()


# ---------------------------------------------------------------- engine behavior

def test_offline_no_network_when_no_key_and_not_online(tmp_path):
    designer = make_engine(tmp_path)
    assert designer.has_any_key() is False
    with mock.patch("modules.ai_image_designer.requests.post") as post, \
         mock.patch("modules.image_generator.generate_image_bytes") as poll:
        result = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=False,
        )
    assert result is None
    post.assert_not_called()
    poll.assert_not_called()  # offline promise: keyless generator not pinged either


def test_auto_uses_the_provider_with_a_key_when_online(tmp_path):
    designer = make_engine(tmp_path, env={"XAI_API_KEY": "xai-key-123456"})
    response = mock.Mock(status_code=200)
    response.json.return_value = {"data": [{"b64_json": B64_PNG}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=response) as post:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", ["fast"], "#E8B54A", "#0F172A",
            allow_network=True,
        )
    assert shot is not None and shot["provider"] == "xai_grok"
    assert post.call_args.args[0] == "https://api.x.ai/v1/images/generations"


def test_auto_mode_stays_offline_for_offline_campaigns_even_with_a_key(tmp_path):
    """THE offline promise: a saved key (e.g. for text use) must not make an
    offline campaign touch the network in auto mode. Regression for the
    net_audit zero-outbound-requests contract."""
    designer = make_engine(tmp_path, env={"GEMINI_API_KEY": "g-key-12345678"})
    assert designer.has_any_key() is True
    assert designer.network_allowed(online_connected=False) is False
    with mock.patch("modules.ai_image_designer.requests.post") as post, \
         mock.patch("modules.image_generator.generate_image_bytes") as poll:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=False,
        )
    assert shot is None
    post.assert_not_called()
    poll.assert_not_called()


def test_explicit_image_provider_opts_in_even_when_text_offline(tmp_path):
    """Picking a concrete image provider in Settings is an explicit opt-in:
    image calls are allowed even while the text provider is offline."""
    designer = make_engine(
        tmp_path, env={"GEMINI_API_KEY": "g-key-12345678"},
        config={"image_provider": "gemini"},
    )
    assert designer.network_allowed(online_connected=False) is True
    ok = mock.Mock(status_code=200)
    ok.json.return_value = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": B64_PNG}}]}}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=ok) as post:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=False,  # campaign offline — explicit provider still allowed
        )
    assert shot is not None and shot["provider"] == "gemini"
    assert post.call_count == 1


def test_model_fallback_chain_on_404(tmp_path):
    designer = make_engine(tmp_path, env={"GEMINI_API_KEY": "g-key-12345678"})
    ok = mock.Mock(status_code=200)
    ok.json.return_value = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": B64_PNG}}]}}]}
    bad = mock.Mock(status_code=404)
    with mock.patch("modules.ai_image_designer.requests.post", side_effect=[bad, ok]) as post:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=True,  # online campaign — auto mode may use the key
        )
    assert shot is not None
    assert shot["model"] == IMAGE_PROVIDERS["gemini"]["fallback_models"][0]
    assert post.call_count == 2


def test_provider_setting_off_disables_keyed_providers(tmp_path):
    designer = make_engine(tmp_path, env={"GEMINI_API_KEY": "g-key-12345678"},
                           config={"image_provider": "off"})
    with mock.patch("modules.ai_image_designer.requests.post") as post:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=False,
        )
    assert shot is None
    post.assert_not_called()


def test_keyless_fallback_used_when_online(tmp_path):
    designer = make_engine(tmp_path, env={"BRANDFORGE_PUBLIC_IMAGES":"1"})  # explicit public-service consent
    with mock.patch("modules.image_generator.generate_image_bytes", return_value=tiny_png()) as poll:
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=True,
        )
    assert shot is not None and shot["provider"] == "pollinations"
    assert poll.call_count == 1


def test_bad_payload_never_shipped(tmp_path):
    """A provider answering 200 with non-image bytes must not produce a file."""
    designer = make_engine(tmp_path, env={"GEMINI_API_KEY": "g-key-12345678"})
    ok = mock.Mock(status_code=200)
    ok.json.return_value = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"garbage!!" * 40).decode()}}]}}]}
    with mock.patch("modules.ai_image_designer.requests.post", return_value=ok):
        shot = designer.generate_design_image(
            "Brand", "Retail", "Shoppers", None, "#E8B54A", "#0F172A",
            allow_network=False,
        )
    assert shot is None


# ---------------------------------------------------------------- compositing

def test_photo_hero_composite_renders_and_carries_brand():
    import resvg_py
    v = VisualDesigner()
    svg = v.generate_photo_hero_svg(
        tiny_png(600, 315), "Sindh Ceramics",
        "Hand-glazed tiles for interior architects",
        primary_color="#C2410C", secondary_color="#1C1917",
        brand_text="SINDH CERAMICS",
        benefits=["40-year lifespan", "Hand-glazed craft"],
        cta_text="See the Collection",
    )
    assert "data:image/png;base64," in svg
    assert "Sindh Ceramics" in svg and "SINDH CERAMICS" in svg
    assert "#C2410C" in svg
    assert "40-year lifespan" in svg
    assert 'width="696" height="630"' in svg and 'fill="#1C1917"' in svg  # opaque measured text panel
    png = resvg_py.svg_to_bytes(svg_string=svg)
    assert png.startswith(b"\x89PNG") and len(png) > 1000


def test_photo_square_composite_renders():
    import resvg_py
    v = VisualDesigner()
    svg = v.generate_photo_square_svg(
        tiny_png(400, 400), "Sindh Ceramics", "Hand-glazed craft",
        primary_color="#C2410C", secondary_color="#1C1917",
        brand_text="SINDH CERAMICS",
        benefits=["40-year lifespan", "Hand-glazed craft"],
    )
    png = resvg_py.svg_to_bytes(svg_string=svg)
    assert png.startswith(b"\x89PNG")


def test_photo_composite_escapes_hostile_text():
    v = VisualDesigner()
    svg = v.generate_photo_hero_svg(
        tiny_png(60, 40), '<script>alert(1)</script>', '"><svg onload=alert(1)>',
    )
    assert "<script>" not in svg
    assert "<svg onload" not in svg  # raw injection blocked; escaped literal text is fine


# ---------------------------------------------------------------- swarm integration

def test_swarm_campaign_uses_ai_hero_when_available(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    prev_data_dir = os.environ.get("BRANDFORGE_DATA_DIR")
    os.environ["BRANDFORGE_DATA_DIR"] = str(data_dir)
    try:
        from engines.ai_engine import get_engine
        from modules.swarm_director import SwarmDirector
        eng = get_engine(provider="offline")
        director = SwarmDirector(eng)
        shot = {"bytes": tiny_png(600, 315), "provider": "gemini", "model": "gemini-3-pro-image-preview"}
        with mock.patch("modules.ai_image_designer.AIImageDesigner") as designer_cls:
            instance = designer_cls.return_value
            instance.has_any_key.return_value = True
            instance.generate_design_image.return_value = shot
            res = director.execute_swarm_campaign(
                product_name="Sindh Ceramics", industry="Handmade Tiles",
                target_audience="Interior Architects",
                key_benefits="40-year lifespan, hand-glazed craft", lang="en",
            )
        vf = res["visual_files"]
        assert vf.get("hero_ai.png", b"").startswith(b"\x89PNG")
        assert vf.get("hero_ai.jpg", b"")[:2] == b"\xff\xd8"
        assert vf.get("hero_image.jpg") == tiny_png(600, 315)
        assert res["meta"]["ai_image"] is True
        assert res["meta"]["image_provider"] == "gemini"
        # deterministic template deliverables still present
        assert "hero_banner.svg" in vf
    finally:
        if prev_data_dir is None:
            os.environ.pop("BRANDFORGE_DATA_DIR", None)
        else:
            os.environ["BRANDFORGE_DATA_DIR"] = prev_data_dir


def test_swarm_campaign_stays_offline_without_keys(tmp_path):
    data_dir = tmp_path / "data2"
    data_dir.mkdir()
    prev_data_dir = os.environ.get("BRANDFORGE_DATA_DIR")
    os.environ["BRANDFORGE_DATA_DIR"] = str(data_dir)
    try:
        from engines.ai_engine import get_engine
        from modules.swarm_director import SwarmDirector
        eng = get_engine(provider="offline")
        director = SwarmDirector(eng)
        with mock.patch("modules.ai_image_designer.requests.post") as post, \
             mock.patch("modules.image_generator.generate_image_bytes") as poll:
            res = director.execute_swarm_campaign(
                product_name="Brand", industry="Retail",
                target_audience="Shoppers", key_benefits="a, b", lang="en",
            )
        post.assert_not_called()
        poll.assert_not_called()
        assert res["meta"]["ai_image"] is False
        assert res["meta"]["image_provider"] is None
        assert "hero_ai.png" not in res["visual_files"]
    finally:
        if prev_data_dir is None:
            os.environ.pop("BRANDFORGE_DATA_DIR", None)
        else:
            os.environ["BRANDFORGE_DATA_DIR"] = prev_data_dir
