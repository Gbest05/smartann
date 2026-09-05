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
        return db.session.get(User, int(user_id))

    # Health Check Endpoint for Cloud Platforms / Load Balancers
    @app.route('/healthz')
    def health_check():
        return {'status': 'healthy', 'service': 'smart-energy-management'}, 200

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


def _ensure_startup_data(app_instance):
    """Ensure database tables and essential initial configurations exist without overwriting."""
    with app_instance.app_context():
        try:
            db.create_all()
            from app.models import User, SystemSetting, Recommendation

            # 1. System Settings Defaults
            settings_defaults = [
                ('tariff_per_kwh', '120.0', 'Electricity tariff rate in Nigerian Naira per kWh (NGN/kWh)'),
                ('low_consumption_threshold', '5.0', 'Daily consumption threshold in kWh for Low tier (Green)'),
                ('moderate_consumption_threshold', '10.0', 'Daily consumption threshold in kWh for Moderate tier (Amber)')
            ]
            for key, val, desc in settings_defaults:
                if not SystemSetting.query.filter_by(key=key).first():
                    db.session.add(SystemSetting(key=key, value=val, description=desc))

            # 2. Ensure initial administrator if no admin exists
            if not User.query.filter_by(role='admin').first():
                admin_email = os.environ.get('ADMIN_EMAIL', 'admin@energy.test').lower().strip()
                admin_pass = os.environ.get('ADMIN_PASSWORD', 'AdminPass123!')
                admin_name = os.environ.get('ADMIN_NAME', 'Project Administrator')
                admin = User(full_name=admin_name, email=admin_email, role='admin')
                admin.set_password(admin_pass)
                db.session.add(admin)

            # 3. Default recommendation rules
            if not Recommendation.query.first():
                recs_data = [
                    ("Air Conditioning Temperature Optimization", "Keep cooling thermostats set to 24°C-26°C. Each degree below 24°C increases electricity consumption by 6-8%.", "high", "bi-snow"),
                    ("Water Heater Operating Schedule", "Switch off electric water heaters once warm. Avoid continuous 24-hour boiling standby.", "high", "bi-fire"),
                    ("Off-Peak Appliance Scheduling", "Operate washing machines, pumping machines, and iron boxes during off-peak morning hours.", "moderate", "bi-clock-history"),
                    ("LED Lighting Transition", "Ensure all room fixtures use energy-efficient LED luminaires instead of halogen or incandescent bulbs.", "moderate", "bi-lightbulb-fill"),
                    ("Natural Cross-Ventilation", "Open windows in the early morning and evening to cool interior rooms naturally.", "low", "bi-wind")
                ]
                for title, msg, tier, icon in recs_data:
                    db.session.add(Recommendation(title=title, message=msg, consumption_level=tier, icon=icon, is_active=True))

            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app_instance.logger.warning(f"Startup database initialization: {exc}")


# Module-level __getattr__ for WSGI servers and cloud deployments (e.g. Render running 'gunicorn app:app')
def __getattr__(name: str):
    if name == 'app':
        global _wsgi_app
        try:
            return _wsgi_app
        except NameError:
            target_env = os.environ.get('FLASK_ENV', 'production' if os.environ.get('RENDER') else 'default')
            _wsgi_app = create_app(target_env)
            _ensure_startup_data(_wsgi_app)
            return _wsgi_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


