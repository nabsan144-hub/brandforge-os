"""Bounded web artwork and portable source, not semantic recovery of AI text."""
import base64
import io
import json
import re
from xml.sax.saxutils import escape
from PIL import Image


class ArtworkConfigurationError(ValueError):
    """Safe preflight error; no external generation has started."""


def validate_reference_uri(uri):
    try:
        if not isinstance(uri, str) or len(uri) > 330000 or not re.fullmatch(r'data:image/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}', uri):
            raise ValueError('Invalid reference')
        data = base64.b64decode(uri.split(',')[1], validate=True)
        if len(data) > 220000:
            raise ValueError('Reference capacity')
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG', 'JPEG') or im.width*im.height > 4000000 or getattr(im, 'n_frames', 1) != 1 or not uri.startswith('data:image/' + im.format.lower() + ';'):
                raise ValueError('Invalid raster')
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
        return uri
    except Exception as exc:
        raise ArtworkConfigurationError('Use a complete PNG or JPEG reference, prepared below 220 KB and 4 million pixels. No image was sent.') from exc


class ArtworkGenerationError(RuntimeError):
    """Public, credential-free error for an incomplete AI campaign."""


def artwork_documents(raw, name, width, height, watermark, sections=None):
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        image = source.convert('RGB')
        image.thumbnail((1440, 1440))
        for quality in (85, 75, 65, 55):
            stream = io.BytesIO()
            image.save(stream, format='JPEG', quality=quality)
            data = stream.getvalue()
            if len(data) <= 220000:
                break
    if len(data) > 220000:
        raise ValueError('AI artwork exceeds portable source capacity.')
    uri = 'data:image/jpeg;base64,' + base64.b64encode(data).decode('ascii')
    d = {'format': 'brandforge-canvas', 'version': 1, 'name': str(name).encode('utf-16-le')[:160].decode('utf-16-le', errors='ignore'),
         'width': width, 'height': height, 'background': '#101820', 'watermark': bool(watermark),
         'sections': {k: str((sections or {}).get(k, ''))[:20000] for k in ('strategy', 'copy', 'seo')},
         'layers': [{'id': 'ai-artwork', 'type': 'image', 'x': 0, 'y': 0, 'width': width, 'height': height,
                     'rotation': 0, 'opacity': 1, 'fill': '#ffffff', 'src': uri, 'fit': 'contain', 'anchor': 'xMidYMid'}]}
    # Validate with the actual Desktop portable-source validator before saving.
    from modules.canvas_projects import validate_document
    validate_document(d)
    footer = ''
    if watermark:
        footer = f'<rect y="{height-30}" width="{width}" height="30" fill="#102033"/><text x="{width/2}" y="{height-10}" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="16">Made with BrandForge</text>'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(str(name), {chr(34): "&quot;"})}"><rect width="100%" height="100%" fill="#101820"/><image href="{uri}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet"/>{footer}</svg>'
    return svg, json.dumps(d, ensure_ascii=False), data
