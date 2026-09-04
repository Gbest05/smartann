import os
from datetime import datetime
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from config import config, Config
from app.models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_name: str = None) -> Flask:
    """Application factory for Smart Energy Management System."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, Config))

    # Initialize Extensions
    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Configure Login Manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access your energy management portal.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.energy import energy_bp
    from app.routes.prediction import prediction_bp
    from app.routes.admin import admin_bp
    from app.routes.reports import reports_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(energy_bp)
    app.register_blueprint(prediction_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)

    # Custom Jinja Template Filters
    from app.utils.helpers import format_naira, classify_consumption

    @app.template_filter('naira')
    def naira_filter(amount):
        return format_naira(amount)

    @app.template_filter('consumption_badge')
    def consumption_badge_filter(level_or_kwh):
        if isinstance(level_or_kwh, (int, float)):
            level = classify_consumption(level_or_kwh)
        else:
            level = str(level_or_kwh).capitalize()

        if level == 'Low':
            return 'bg-emerald-600 text-white'
        elif level == 'Moderate':
            return 'bg-amber-500 text-white'
        elif level == 'High':
            return 'bg-red-600 text-white'
        return 'bg-secondary text-white'

    # Template Global Context Processors
    @app.context_processor
    def inject_global_vars():
        from app.utils.helpers import get_landing_content
        landing_info = get_landing_content()
        return {
            'current_year': datetime.now().year,
            'app_name': landing_info.get('brand_name', 'SmartEnergy AI'),
            'brand_badge': landing_info.get('brand_badge', 'ANN'),
            'currency_symbol': '₦'
        }

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
