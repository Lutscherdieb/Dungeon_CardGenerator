"""CardGenerator: print-ready boardgame cards at exact MakePlayingCards measurements.

Package layout (see docs/ARCHITECTURE.md):

    spec/    print geometry -- the single source of truth for every pixel size
    model/   the card definition -- one pydantic union, feeding schemas and DB
    render/  HTML -> PNG pipeline: templates, Playwright, crops
    store/   SQLAlchemy models and session
    web/     the local gallery server
"""

__version__ = "0.1.0.dev0"
