"""
Shared utility functions.
"""

import os
import re


def safe_filename(text: str) -> str:
    """Replace filesystem-unsafe chars with underscore."""
    return re.sub(r'[<>:"/\\|?*]', '_', text).strip('. ')


def unique_path(directory: str, base_name: str, ext: str) -> str:
    """Return a path like ``dir/base_name.ext``, appending _1, _2 … if needed."""
    safe = safe_filename(base_name)
    path = os.path.join(directory, f"{safe}{ext}")
    if not os.path.exists(path):
        return path
    counter = 1
    while True:
        path = os.path.join(directory, f"{safe}_{counter}{ext}")
        if not os.path.exists(path):
            return path
        counter += 1
