"""Templates package — each module exposes ``NAME: str`` and ``render(ctx, r)``.

The CLI auto-discovers every ``.py`` file in this package at startup and
registers ``{NAME: render}``. There is no central list to keep in sync — the
filesystem is the registry.
"""
