from flask import request, current_app
from app.models import db, ActivityLog, SystemSetting


def format_naira(amount) -> str:
    """Format a numeric value as Nigerian Naira currency (₦)."""
    try:
        val = float(amount) if amount is not None else 0.0
        return f"₦{val:,.2f}"
    except (ValueError, TypeError):
        return "₦0.00"


def get_system_setting(key: str, default_val: str) -> str:
    """Retrieve a system setting value from the database or return default."""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting and setting.value:
            return setting.value
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return default_val


def set_system_setting(key: str, value: str, description: str = None):
    """Save or update a system setting in the database."""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        if not setting:
            setting = SystemSetting(key=key, value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.value = str(value)
            if description:
                setting.description = description
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def get_landing_content() -> dict:
    """Retrieve customizable landing page headlines, text, and branding."""
    defaults = {
        'brand_name': 'SmartEnergy AI',
        'brand_badge': 'ANN',
        'hero_badge': 'Artificial Neural Network (MLPRegressor) Powered',
        'hero_title': 'Smart Energy Management for Smarter Homes',
        'hero_subtitle': 'Monitor your electricity consumption, predict future energy usage, and discover smarter ways to reduce energy costs using Artificial Neural Networks.',
        'hero_cta_text': 'Get Started',
        'hero_subtext': 'Zero Hardware Required • Intelligent Residential Energy Optimization',
        
        # Features
        'feature1_title': 'Smart Energy Monitoring',
        'feature1_desc': 'Record and track total daily, peak, and off-peak electricity consumption (kWh) with automated cost calculations in Nigerian Naira (₦).',
        'feature2_title': 'ANN Energy Prediction',
        'feature2_desc': 'Multi-Layer Perceptron neural networks analyze historical usage patterns and operational variables to forecast future electricity demand.',
        'feature3_title': 'Consumption Analytics',
        'feature3_desc': 'Interactive time-series visualizations, peak load distributions, and predicted vs actual consumption comparative metrics.',
        'feature4_title': 'Smart Recommendations',
        'feature4_desc': 'Dynamic, multi-tier energy conservation recommendations customized to your household\'s active consumption tier (Low, Moderate, High).',
        
        # Benefits / Impact Section
        'impact_title': 'Empowering Households with AI-Driven Energy Efficiency',
        'impact_subtitle': 'Actionable insights to eliminate peak-load surges and lower monthly electricity bills.',
        'benefit1_title': 'Reduce Unnecessary Energy Draw',
        'benefit1_desc': 'Pinpoint heavy appliance loads and eliminate phantom power draws before high utility bills arrive.',
        'benefit2_title': 'Understand Peak vs Off-Peak Patterns',
        'benefit2_desc': 'Clear visibility into operational energy splits to balance heavy appliance usage schedules.',
        'benefit3_title': 'Forecast Future Electricity Expenses',
        'benefit3_desc': 'Harness neural network regression models to forecast next-day and monthly energy demands accurately.',
        'benefit4_title': 'Make Better Energy Decisions',
        'benefit4_desc': 'Empirical data insights and customized advisory help households budget electricity tokens proactively.',
        
        # Live Impact Card
        'card_title': 'Household Energy Impact & Cost Savings',
        'card_stat1_label': 'Average Cost Reduction',
        'card_stat1_val': 'Up to 28.4%',
        'card_stat2_label': 'ANN Forecast Accuracy',
        'card_stat2_val': '99.2% R² Score',
        'card_desc': 'Get real-time insights, proactive peak-hour alerts, and neural network forecasts tailored to your household habits.'
    }

    result = {}
    try:
        for key, def_val in defaults.items():
            result[key] = get_system_setting(key, def_val)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return defaults
    return result


def get_active_tariff() -> float:
    """Get the active electricity tariff rate per kWh in Naira."""
    default_tariff = str(current_app.config.get('DEFAULT_TARIFF_PER_KWH', 120.0))
    val = get_system_setting('tariff_per_kwh', default_tariff)
    try:
        return float(val)
    except (ValueError, TypeError):
        return 120.0


def get_system_thresholds() -> tuple[float, float]:
    """Get (low_threshold, moderate_threshold) in kWh."""
    low_default = str(current_app.config.get('LOW_CONSUMPTION_THRESHOLD', 5.0))
    mod_default = str(current_app.config.get('MODERATE_CONSUMPTION_THRESHOLD', 10.0))
    
    low_val = get_system_setting('low_consumption_threshold', low_default)
    mod_val = get_system_setting('moderate_consumption_threshold', mod_default)
    
    try:
        low_f = float(low_val)
    except (ValueError, TypeError):
        low_f = 5.0
        
    try:
        mod_f = float(mod_val)
    except (ValueError, TypeError):
        mod_f = 10.0
        
    return low_f, mod_f


def calculate_cost(kwh: float, tariff: float = None) -> float:
    """Calculate estimated electricity cost given kWh and tariff rate."""
    if tariff is None:
        tariff = get_active_tariff()
    try:
        return round(float(kwh) * float(tariff), 2)
    except (ValueError, TypeError):
        return 0.0


def classify_consumption(kwh: float) -> str:
    """Classify energy usage into Low, Moderate, or High."""
    try:
        kwh_val = float(kwh)
    except (ValueError, TypeError):
        return 'Moderate'
        
    low_th, mod_th = get_system_thresholds()
    if kwh_val <= low_th:
        return 'Low'
    elif kwh_val <= mod_th:
        return 'Moderate'
    return 'High'


def log_activity(user_id: int, action: str, description: str, ip_address: str = None):
    """Record an audit trail activity log in the database."""
    try:
        if ip_address is None and request:
            ip_address = request.remote_addr

        log_entry = ActivityLog(
            user_id=user_id,
            action=action.upper(),
            description=description,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.warning(f"Could not log activity: {e}")
