def humanbytes(size):
    if not size:
        return "0 B"
    try:
        size = float(size)
    except (ValueError, TypeError):
        return "0 B"
    if size <= 0:
        return "0 B"
    power = 1024
    n = 0
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    while size >= power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}" if n > 0 else f"{int(size)} {units[n]}"
