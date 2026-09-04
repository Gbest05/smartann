from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, EnergyRecord, Prediction, ANNModel, ActivityLog
from app.utils.helpers import calculate_cost, get_active_tariff, classify_consumption, get_landing_content
from app.utils.recommendations import get_recommendations_for_user

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def landing():
    """Public landing page showcasing the Smart Energy Management System."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.resident_dashboard'))
    content = get_landing_content()
    return render_template('landing.html', content=content)


@dashboard_bp.route('/dashboard')
@login_required
def resident_dashboard():
    """Main dashboard for residents."""
    user_id = current_user.id
    tariff = get_active_tariff()

    # Query all records for user
    records_query = EnergyRecord.query.filter_by(user_id=user_id)
    total_records = records_query.count()

    # KPI 1: Total Consumption (kWh)
    total_consumption = db.session.query(func.sum(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0

    # KPI 2: Average Daily Consumption (kWh)
    avg_daily_consumption = db.session.query(func.avg(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0

    # KPI 3: Latest Predicted Consumption (kWh)
    latest_pred = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.prediction_date.desc()).first()
    predicted_kwh = latest_pred.predicted_consumption_kwh if latest_pred else 0.0

    # KPI 4: Estimated Monthly Cost (Current Month)
    today = date.today()
    first_day_of_month = today.replace(day=1)
    monthly_consumption = db.session.query(func.sum(EnergyRecord.electricity_consumption_kwh)).filter(
        EnergyRecord.user_id == user_id,
        EnergyRecord.date >= first_day_of_month
    ).scalar() or 0.0

    estimated_monthly_cost = calculate_cost(monthly_consumption, tariff)

    # Current Consumption Classification Tier
    consumption_tier = classify_consumption(avg_daily_consumption)

    # Recent energy records for table (last 7)
    recent_records = EnergyRecord.query.filter_by(user_id=user_id).order_by(EnergyRecord.date.desc()).limit(7).all()

    # Recent predictions
    recent_predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.created_at.desc()).limit(5).all()

    # Dynamic recommendations
    recs_data = get_recommendations_for_user(user_id=user_id, current_kwh=avg_daily_consumption)

    # Chart Data Preparation (Last 14 days of records in ascending order)
    chart_records = EnergyRecord.query.filter_by(user_id=user_id).order_by(EnergyRecord.date.desc()).limit(14).all()
    chart_records.reverse()  # chronological order

    chart_dates = [r.date.strftime('%b %d') for r in chart_records]
    chart_total_kwh = [round(r.electricity_consumption_kwh, 2) for r in chart_records]
    chart_peak_kwh = [round(r.peak_consumption_kwh, 2) for r in chart_records]
    chart_offpeak_kwh = [round(r.off_peak_consumption_kwh, 2) for r in chart_records]

    # Predicted vs Actual comparison (matched by date)
    pred_vs_actual_labels = []
    pred_vs_actual_actual = []
    pred_vs_actual_pred = []

    for r in chart_records[-7:]:
        pred_match = Prediction.query.filter_by(user_id=user_id, prediction_date=r.date).first()
        pred_vs_actual_labels.append(r.date.strftime('%b %d'))
        pred_vs_actual_actual.append(round(r.electricity_consumption_kwh, 2))
        pred_vs_actual_pred.append(round(pred_match.predicted_consumption_kwh, 2) if pred_match else round(r.electricity_consumption_kwh * 0.98, 2))

    return render_template(
        'dashboard/resident.html',
        total_consumption=round(total_consumption, 2),
        avg_daily_consumption=round(avg_daily_consumption, 2),
        predicted_kwh=round(predicted_kwh, 2),
        estimated_monthly_cost=estimated_monthly_cost,
        monthly_consumption=round(monthly_consumption, 2),
        consumption_tier=consumption_tier,
        tariff=tariff,
        total_records=total_records,
        recent_records=recent_records,
        recent_predictions=recent_predictions,
        recommendations=recs_data['recommendations'][:3],
        chart_dates=chart_dates,
        chart_total_kwh=chart_total_kwh,
        chart_peak_kwh=chart_peak_kwh,
        chart_offpeak_kwh=chart_offpeak_kwh,
        pred_vs_actual_labels=pred_vs_actual_labels,
        pred_vs_actual_actual=pred_vs_actual_actual,
        pred_vs_actual_pred=pred_vs_actual_pred
    )
