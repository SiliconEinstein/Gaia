"""Static assets bundled with `gaia inspect starmap`.

Holds the single-file HTML template (`template.html`) into which the
CLI injects a JSON graph payload. The current template is a minimal
placeholder; a richer interactive bundle replaces it later without
any change to the CLI plumbing as long as the
``<!--__GRAPH_DATA__-->`` placeholder is preserved in ``<head>``.
"""
