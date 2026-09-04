import csv
import io
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, Response, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from app.models import db, EnergyRecord, Prediction, User
from app.utils.helpers import get_active_tariff, calculate_cost, format_naira, classify_consumption
from app.utils.recommendations import get_recommendations_for_user

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports')
@login_required
def index():
    """Reports overview with dynamic filtering (Daily, Weekly, Monthly, Summary)."""
    report_type = request.args.get('type', 'monthly')  # 'daily', 'weekly', 'monthly', 'summary'
    user_id = request.args.get('user_id', type=int)
    tariff = get_active_tariff()

    # Scope
    if not current_user.is_admin or not user_id:
        user_id = current_user.id
        target_user = current_user
    else:
        target_user = User.query.get(user_id) or current_user

    # Base query
    query = EnergyRecord.query.filter_by(user_id=user_id)

    # Aggregates
    total_kwh = db.session.query(func.sum(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    avg_kwh = db.session.query(func.avg(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    max_kwh = db.session.query(func.max(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    min_kwh = db.session.query(func.min(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    peak_sum = db.session.query(func.sum(EnergyRecord.peak_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    off_peak_sum = db.session.query(func.sum(EnergyRecord.off_peak_consumption_kwh)).filter_by(user_id=user_id).scalar() or 0.0
    total_cost = db.session.query(func.sum(EnergyRecord.estimated_cost)).filter_by(user_id=user_id).scalar() or 0.0

    # Grouped records based on report type
    grouped_data = []

    if report_type == 'daily':
        # Last 30 daily records
        daily_records = query.order_by(EnergyRecord.date.desc()).limit(30).all()
        for r in daily_records:
            grouped_data.append({
                'period': r.date.strftime('%B %d, %Y'),
                'total_kwh': r.electricity_consumption_kwh,
                'peak_kwh': r.peak_consumption_kwh,
                'off_peak_kwh': r.off_peak_consumption_kwh,
                'cost': r.estimated_cost,
                'level': r.consumption_level
            })

    elif report_type == 'weekly':
        # Group by week (last 12 weeks)
        all_records = query.order_by(EnergyRecord.date.asc()).all()
        weeks_dict = {}
        for r in all_records:
            # Year-Week identifier
            yw = r.date.strftime('%Y-W%W')
            if yw not in weeks_dict:
                weeks_dict[yw] = {
                    'period': f"Week {r.date.strftime('%W, %Y')} (starting {r.date.strftime('%b %d')})",
                    'total_kwh': 0.0,
                    'peak_kwh': 0.0,
                    'off_peak_kwh': 0.0,
                    'cost': 0.0,
                    'count': 0
                }
            weeks_dict[yw]['total_kwh'] += r.electricity_consumption_kwh
            weeks_dict[yw]['peak_kwh'] += r.peak_consumption_kwh
            weeks_dict[yw]['off_peak_kwh'] += r.off_peak_consumption_kwh
            weeks_dict[yw]['cost'] += r.estimated_cost
            weeks_dict[yw]['count'] += 1

        for k in sorted(weeks_dict.keys(), reverse=True)[:12]:
            w = weeks_dict[k]
            avg_daily = w['total_kwh'] / max(1, w['count'])
            grouped_data.append({
                'period': w['period'],
                'total_kwh': round(w['total_kwh'], 2),
                'peak_kwh': round(w['peak_kwh'], 2),
                'off_peak_kwh': round(w['off_peak_kwh'], 2),
                'cost': round(w['cost'], 2),
                'level': classify_consumption(avg_daily)
            })

    else:  # monthly
        # Group by Month
        all_records = query.order_by(EnergyRecord.date.asc()).all()
        months_dict = {}
        for r in all_records:
            ym = r.date.strftime('%Y-%m')
            if ym not in months_dict:
                months_dict[ym] = {
                    'period': r.date.strftime('%B %Y'),
                    'total_kwh': 0.0,
                    'peak_kwh': 0.0,
                    'off_peak_kwh': 0.0,
                    'cost': 0.0,
                    'count': 0
                }
            months_dict[ym]['total_kwh'] += r.electricity_consumption_kwh
            months_dict[ym]['peak_kwh'] += r.peak_consumption_kwh
            months_dict[ym]['off_peak_kwh'] += r.off_peak_consumption_kwh
            months_dict[ym]['cost'] += r.estimated_cost
            months_dict[ym]['count'] += 1

        for k in sorted(months_dict.keys(), reverse=True)[:12]:
            m = months_dict[k]
            avg_daily = m['total_kwh'] / max(1, m['count'])
            grouped_data.append({
                'period': m['period'],
                'total_kwh': round(m['total_kwh'], 2),
                'peak_kwh': round(m['peak_kwh'], 2),
                'off_peak_kwh': round(m['off_peak_kwh'], 2),
                'cost': round(m['cost'], 2),
                'level': classify_consumption(avg_daily)
            })

    users_list = User.query.all() if current_user.is_admin else []

    return render_template(
        'reports/index.html',
        report_type=report_type,
        grouped_data=grouped_data,
        target_user=target_user,
        users=users_list,
        selected_user_id=user_id,
        total_kwh=round(total_kwh, 2),
        avg_kwh=round(avg_kwh, 2),
        max_kwh=round(max_kwh, 2),
        min_kwh=round(min_kwh, 2),
        peak_sum=round(peak_sum, 2),
        off_peak_sum=round(off_peak_sum, 2),
        total_cost=total_cost,
        tariff=tariff
    )


@reports_bp.route('/reports/print')
@login_required
def print_view():
    """Print-friendly report view formatted for physical printing or PDF generation."""
    report_type = request.args.get('type', 'monthly')
    user_id = request.args.get('user_id', type=int) or current_user.id
    target_user = User.query.get(user_id) or current_user

    # Fetch report records
    records = EnergyRecord.query.filter_by(user_id=user_id).order_by(EnergyRecord.date.desc()).limit(60).all()
    total_kwh = sum(r.electricity_consumption_kwh for r in records)
    total_cost = sum(r.estimated_cost for r in records)
    avg_kwh = (total_kwh / len(records)) if records else 0.0

    return render_template(
        'reports/print_view.html',
        target_user=target_user,
        report_type=report_type,
        records=records,
        total_kwh=round(total_kwh, 2),
        total_cost=round(total_cost, 2),
        avg_kwh=round(avg_kwh, 2),
        generated_at=datetime.now().strftime('%B %d, %Y %I:%M %p')
    )


@reports_bp.route('/reports/export-csv')
@login_required
def export_csv():
    """Export consumption records to CSV."""
    user_id = request.args.get('user_id', type=int)
    if not current_user.is_admin or not user_id:
        user_id = current_user.id

    records = EnergyRecord.query.filter_by(user_id=user_id).order_by(EnergyRecord.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Date', 'Electricity Consumption (kWh)',
        'Peak Consumption (kWh)', 'Off-Peak Consumption (kWh)',
        'Appliance Usage (Hours)', 'Estimated Cost (NGN)',
        'Consumption Level', 'Is Demo Data'
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.date.strftime('%Y-%m-%d'),
            f"{r.electricity_consumption_kwh:.2f}",
            f"{r.peak_consumption_kwh:.2f}",
            f"{r.off_peak_consumption_kwh:.2f}",
            f"{r.appliance_usage_hours:.1f}",
            f"{r.estimated_cost:.2f}",
            r.consumption_level,
            "Yes" if r.is_synthetic else "No"
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=energy_report_{date.today()}.csv"}
    )


@reports_bp.route('/recommendations')
@login_required
def recommendations():
    """Detailed Energy-Saving Recommendations Page."""
    recs_data = get_recommendations_for_user(user_id=current_user.id)
    return render_template(
        'recommendations/index.html',
        recs_data=recs_data
    )
