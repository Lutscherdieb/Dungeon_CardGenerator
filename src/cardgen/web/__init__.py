"""The local gallery: a CherryPy app over the card store."""

from .queue import RENDER_QUEUE, RenderQueue

__all__ = ["RENDER_QUEUE", "RenderQueue", "serve"]


def serve(*args, **kwargs):
    """Start the gallery. Imported lazily so `import cardgen.web` stays cheap."""
    from .app import serve as _serve

    return _serve(*args, **kwargs)
