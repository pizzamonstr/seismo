"""Headline number tiles that sit in a grid and wrap on phones."""

import streamlit as st

TILE_STYLE = """
<style>
.tile-grid {
    display: grid;
    gap: 1rem;
    margin-bottom: 1rem;
}
.tile-label {
    font-size: 0.875rem;
    margin-bottom: 0.25rem;
}
.tile-value {
    font-size: 2.25rem;
    line-height: 1.2;
}
@media (max-width: 640px) {
    .tile-grid {
        grid-template-columns: 1fr 1fr !important;
    }
    .tile-value {
        font-size: 1.75rem;
    }
}
</style>
"""


def build_tile(label, value):
    """Build one tile: a small label over a big number."""
    return (
        f'<div><div class="tile-label">{label}</div>'
        f'<div class="tile-value">{value}</div></div>'
    )


def show_tile_grid(tiles, per_row):
    """Show tiles in rows, falling back to two per row on phones."""
    cells = ""
    for label, value in tiles:
        cells = cells + build_tile(label, value)
    columns = f"repeat({per_row}, 1fr)"
    st.html(
        TILE_STYLE
        + f'<div class="tile-grid" '
        f'style="grid-template-columns: {columns}">{cells}</div>'
    )