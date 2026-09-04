from datetime import datetime, timedelta, date
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import EnergyRecord, Prediction, ANNModel
from app.ml.predict import predict_energy_consumption

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/charts/consumption-trend')
@login_required
def consumption_trend():
    """API endpoint providing time-series data for interactive charts."""
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 365)  # between 7 and 365 days

    start_date = date.today() - timedelta(days=days)

    if current_user.is_admin and request.args.get('scope') == 'system':
        # System aggregate
        records = EnergyRecord.query.filter(EnergyRecord.date >= start_date)\
            .order_by(EnergyRecord.date.asc()).all()
    else:
        records = EnergyRecord.query.filter(
            EnergyRecord.user_id == current_user.id,
            EnergyRecord.date >= start_date
        ).order_by(EnergyRecord.date.asc()).all()

    dates = [r.date.strftime('%Y-%m-%d') for r in records]
    kwh = [round(r.electricity_consumption_kwh, 2) for r in records]
    peak = [round(r.peak_consumption_kwh, 2) for r in records]
    off_peak = [round(r.off_peak_consumption_kwh, 2) for r in records]

    return jsonify({
        'status': 'success',
        'days': days,
        'dates': dates,
        'consumption_kwh': kwh,
        'peak_kwh': peak,
        'off_peak_kwh': off_peak
    })


@api_bp.route('/predict', methods=['POST'])
@login_required
def api_predict():
    """RESTful API endpoint to request ANN energy consumption prediction."""
    data = request.get_json() or {}
    
    target_date_str = data.get('prediction_date', str(date.today()))
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = date.today()

    appliance_hours = float(data.get('appliance_usage_hours', 8.0))
    peak_kwh = float(data.get('peak_consumption_kwh', 4.0))
    off_peak_kwh = float(data.get('off_peak_consumption_kwh', 3.0))
    baseline = float(data.get('recent_baseline', 8.0)) if data.get('recent_baseline') else None

    result = predict_energy_consumption(
        target_date=target_date,
        appliance_usage_hours=appliance_hours,
        peak_consumption_kwh=peak_kwh,
        off_peak_consumption_kwh=off_peak_kwh,
        recent_baseline=baseline
    )

    return jsonify({
        'status': 'success',
        'prediction': result
    })
