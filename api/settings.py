import os

class Settings:
    def __init__(self):
        self.root = os.path.abspath(os.getcwd())
        self.assets_dir = os.path.join(self.root, 'assets')
        self.templates_dir = os.path.join(self.root, 'templates')
        self.outputs_dir = os.path.join(self.root, 'outputs')
        self.preview_dir = os.path.join(self.root, 'preview')
        self.schemas_dir = os.path.join(self.root, 'schemas')
        # SQLite for dev; swap to Postgres/MySQL via env later
        self.db_url = os.environ.get('DB_URL', f"sqlite:///{os.path.join(self.root,'cards.db')}")
