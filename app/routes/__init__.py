"""Blueprint registry for Smart Energy Management System."""
from .auth import auth_bp
from .dashboard import dashboard_bp
from .energy import energy_bp
from .prediction import prediction_bp
from .admin import admin_bp
from .reports import reports_bp
from .api import api_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'energy_bp',
    'prediction_bp',
    'admin_bp',
    'reports_bp',
    'api_bp'
]
