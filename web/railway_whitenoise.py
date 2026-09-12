"""WhiteNoise middleware that also serves MEDIA_ROOT.

Upstream runs an nginx container beside gunicorn to serve `/static/` and
`/media/` off the same checkout. WhiteNoise covers `STATIC_ROOT` on its own;
NewsBlur's templates address many of the same files through `MEDIA_URL`, so that
prefix is registered here rather than pointing both settings at one URL, which
Django's staticfiles rejects outright.
"""

import os
import re

from django.conf import settings as django_settings
from whitenoise.middleware import WhiteNoiseMiddleware


class WhiteNoiseWithMedia(WhiteNoiseMiddleware):
    def __init__(self, get_response=None, settings=django_settings):
        super().__init__(get_response, settings)
        media_root = getattr(settings, "MEDIA_ROOT", None)
        media_url = getattr(settings, "MEDIA_URL", None)
        if media_root and media_url and os.path.isdir(media_root):
            self.add_files(media_root, prefix=media_url)

    def __call__(self, request):
        # NewsBlur's templates concatenate `{{ MEDIA_URL }}` with a leading-slash
        # path, so every media reference arrives as `/media//img/...`. Upstream's
        # nginx collapses the duplicate; WhiteNoise matches the path verbatim and
        # would 404 every icon on the page.
        path = request.path_info
        if "//" in path:
            collapsed = re.sub(r"/{2,}", "/", path)
            static_file = self.files.get(collapsed)
            if static_file is not None:
                return self.serve(static_file, request)
        return super().__call__(request)
