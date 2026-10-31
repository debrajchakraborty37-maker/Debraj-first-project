import re, copy

def put(ws, ref, val, style=None):
    c = ws[ref] if isinstance(ref, str) else ws.cell(*ref)
    c.value = val
    if style is not None: c._style = copy.copy(style)
    return c

def clear_from(ws, row):
    for m in list(ws.merged_cells.ranges):
        if m.min_row >= row: ws.unmerge_cells(str(m))
    ws.delete_rows(row, max(ws.max_row - row + 2, 1))
    for r in [r for r in ws.row_dimensions if r >= row]: del ws.row_dimensions[r]
