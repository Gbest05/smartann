from app.models import Recommendation, EnergyRecord
from app.utils.helpers import classify_consumption, get_system_thresholds


DEFAULT_RECOMMENDATIONS = {
    'high': [
        {
            'title': 'High Energy Alert & Peak Load Reduction',
            'message': 'Your electricity consumption is higher than recommended. Consider reducing the operating hours of high-energy appliances such as air conditioners, water heaters, and electric stoves during peak hours.',
            'icon': 'bi-exclamation-triangle-fill',
            'badge_class': 'bg-danger'
        },
        {
            'title': 'Air Conditioner & Cooling Optimization',
            'message': 'Air conditioning accounts for up to 50% of residential energy draw. Set cooling thermostats to 24°C-26°C and ensure windows and doors are sealed tightly to minimize compressor strain.',
            'icon': 'bi-snow',
            'badge_class': 'bg-danger'
        },
        {
            'title': 'Phantom Load Elimination',
            'message': 'Appliances in standby mode (TVs, microwaves, sound systems) continuously consume electricity. Use smart power strips or switch them off completely at the wall socket when not in use.',
            'icon': 'bi-plug-fill',
            'badge_class': 'bg-warning'
        }
    ],
    'moderate': [
        {
            'title': 'Moderate Consumption Optimization',
            'message': 'Your energy consumption is within normal limits, but there is opportunity to reduce costs. Running washing machines and heavy appliances during off-peak hours can lower grid strain.',
            'icon': 'bi-speedometer2',
            'badge_class': 'bg-warning'
        },
        {
            'title': 'Lighting & Appliance Efficiency',
            'message': 'Ensure all lighting fixtures use energy-efficient LED bulbs rather than incandescent or halogen bulbs, saving up to 80% on lighting electricity.',
            'icon': 'bi-lightbulb-fill',
            'badge_class': 'bg-success'
        },
        {
            'title': 'Refrigerator Temperature Calibration',
            'message': 'Keep refrigerator temperature at 3°C-5°C and freezer at -18°C. Defrost regularly and avoid placing warm food inside the refrigerator.',
            'icon': 'bi-thermometer-half',
            'badge_class': 'bg-success'
        }
    ],
    'low': [
        {
            'title': 'Excellent Energy Efficiency',
            'message': 'Your household is maintaining an efficient energy consumption profile! Continue your current energy conservation practices to keep electricity costs minimal.',
            'icon': 'bi-check-circle-fill',
            'badge_class': 'bg-success'
        },
        {
            'title': 'Sustain Green Habits',
            'message': 'Maintain natural ventilation and daylighting during daytime hours to further reduce lighting and cooling requirements.',
            'icon': 'bi-tree-fill',
            'badge_class': 'bg-success'
        }
    ]
}


def get_recommendations_for_user(user_id: int = None, current_kwh: float = None) -> dict:
    """Generate dynamic, personalized energy saving recommendations for a resident."""
    # Determine level from provided kWh or recent user records
    level = 'moderate'
    
    if current_kwh is not None:
        level = classify_consumption(current_kwh).lower()
    elif user_id:
        latest_record = EnergyRecord.query.filter_by(user_id=user_id).order_by(EnergyRecord.date.desc()).first()
        if latest_record:
            level = classify_consumption(latest_record.electricity_consumption_kwh).lower()

    # Base list from predefined advice
    tips = list(DEFAULT_RECOMMENDATIONS.get(level, DEFAULT_RECOMMENDATIONS['moderate']))

    # Also query custom recommendations added by admin from database
    try:
        db_recs = Recommendation.query.filter(
            (Recommendation.consumption_level == level) | (Recommendation.consumption_level == 'all'),
            Recommendation.is_active.is_(True)
        ).all()
        for rec in db_recs:
            badge_map = {'high': 'bg-danger', 'moderate': 'bg-warning', 'low': 'bg-success', 'all': 'bg-success'}
            tips.append({
                'title': rec.title,
                'message': rec.message,
                'icon': rec.icon or 'bi-lightning-charge',
                'badge_class': badge_map.get(rec.consumption_level, 'bg-success')
            })
    except Exception:
        pass

    low_th, mod_th = get_system_thresholds()
    return {
        'level': level.capitalize(),
        'low_threshold': low_th,
        'moderate_threshold': mod_th,
        'recommendations': tips
    }
