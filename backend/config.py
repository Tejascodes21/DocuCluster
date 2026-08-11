import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

class Config:
    """Application configuration parameters."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'docucluster_default_secret_key_change_me')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5 MB cap
    TEMP_DIR = Path(os.getenv('TEMP_DIR', BASE_DIR / 'backend' / 'storage' / 'temp')).resolve()
    STORAGE_DIR = Path(os.getenv('STORAGE_DIR', BASE_DIR / 'backend' / 'storage')).resolve()
    
    # Persistent Database URI (SQLite default for standalone, Postgres for production)
    DEFAULT_DB_PATH = STORAGE_DIR / 'docucluster.db'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{DEFAULT_DB_PATH}')
    
    ALLOWED_EXTENSIONS = {'.txt', '.pdf'}
    SESSION_TTL_SECONDS = 3600  # 1 hour TTL for session temporary files

    @classmethod
    def init_app(cls, app):
        """Ensure necessary runtime directories exist."""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        cls.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
