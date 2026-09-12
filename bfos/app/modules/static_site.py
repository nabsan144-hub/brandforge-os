"""Clean HTML URLs for local sales previews and optional /sales mounts.

Downloadable artifacts keep their extensions. Only customer-facing pages and
known legacy tour URLs are canonicalized; unknown paths remain real 404s.
"""
from pathlib import PurePosixPath
from starlette.datastructures import URL
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class SalesStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        local = path.strip('/')
        if local == '.': local = ''
        if any(part.startswith('.') for part in local.split('/')) or local.split('/')[0] in ('tests','node_modules','public') or local in ('package.json','package-lock.json','vercel.json','netlify.toml','build.mjs','tailwind.config.js','tailwind.src.css','_headers','_redirects','assets/product-demo/ASSET-NOTICE.md','assets/product-demo/MUSIC-NOTE.txt','assets/product-demo/manifest.json'):
            raise HTTPException(status_code=404)
        legacy_tour = local in ('assets/product-demo/tour', 'assets/product-demo/tour.html')
        page_html = local.endswith('.html') and '/' not in local and not local.startswith('google') and local != '404.html'
        if legacy_tour or page_html or local == 'index':
            target = 'tour' if legacy_tour else '' if local in ('index', 'index.html') else local[:-5]
            prefix = scope.get('root_path', '').rstrip('/')
            url = URL(scope=scope).replace(path=prefix + '/' + target)
            return RedirectResponse(url, status_code=308)
        if local == 'tour':
            return await super().get_response('assets/product-demo/tour.html', scope)
        if local and not PurePosixPath(local).suffix:
            full, stat = self.lookup_path(local + '.html')
            if stat is not None:
                return await super().get_response(local + '.html', scope)
        return await super().get_response(path, scope)
