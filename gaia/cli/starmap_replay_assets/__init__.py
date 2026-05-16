"""Static assets bundled with `gaia inspect starmap-replay`.

Holds the single-file HTML template (``template.html``) into which the
CLI injects the JSONL timeline payload. Mirrors the
``gaia.cli.starmap_assets`` shipping pattern: ``viz/`` builds a
self-contained bundle, the ship script copies it here, and the CLI
substitutes the ``<!--__TIMELINE_DATA__-->`` placeholder in ``<head>``
with a ``<script>window.TIMELINE_DATA = ...;</script>`` tag at run time.
"""
