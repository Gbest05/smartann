import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
load_dotenv(BASE_DIR / '.env')


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-energy-secret-key-default-2026-nd')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database URI Resolution supporting Neon PostgreSQL & Render PostgreSQL
    raw_db_url = (
        os.environ.get('NEON_DATABASE_URL')
        or os.environ.get('POSTGRES_URL')
        or os.environ.get('POSTGRESQL_URL')
        or os.environ.get('DATABASE_URL')
    )
    if raw_db_url:
        raw_db_url = raw_db_url.strip().strip("'").strip('"')
        if raw_db_url.startswith("psql "):
            raw_db_url = raw_db_url[5:].strip().strip("'").strip('"')
        if raw_db_url.startswith('postgres://'):
            raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)
        if 'neon.tech' in raw_db_url and 'sslmode=' not in raw_db_url:
            separator = '&' if '?' in raw_db_url else '?'
            raw_db_url = f"{raw_db_url}{separator}sslmode=require"
        SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        # Local development fallback to SQLite in instance directory
        instance_dir = BASE_DIR / 'instance'
        instance_dir.mkdir(exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{(instance_dir / "energy.db").as_posix()}'

    # Database connection pooling for PostgreSQL reliability
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Application Business Logic Defaults
    DEFAULT_TARIFF_PER_KWH = float(os.environ.get('DEFAULT_TARIFF_PER_KWH', 120.0))
    LOW_CONSUMPTION_THRESHOLD = float(os.environ.get('LOW_CONSUMPTION_THRESHOLD', 5.0))
    MODERATE_CONSUMPTION_THRESHOLD = float(os.environ.get('MODERATE_CONSUMPTION_THRESHOLD', 10.0))
    
    # ML Models directory
    ML_MODEL_DIR = BASE_DIR / 'app' / 'ml' / 'models'
    
    # Pagination
    ITEMS_PER_PAGE = 15


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig if os.environ.get('FLASK_ENV') == 'production' else DevelopmentConfig
}
