from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, User, EnergyRecord, Prediction, ANNModel, ActivityLog, SystemSetting, Recommendation
from app.forms import SystemSettingsForm, RecommendationForm, UserEditForm
from app.utils.decorators import admin_required
from app.utils.helpers import log_activity, get_active_tariff, get_system_thresholds
from app.ml.train_model import train_ann_model, get_latest_model_metrics

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Administrator Overview Dashboard."""
    # Summary Statistics
    total_users = User.query.count()
    total_residents = User.query.filter_by(role='resident').count()
    total_records = EnergyRecord.query.count()
    total_predictions = Prediction.query.count()

    # System average daily consumption
    avg_system_kwh = db.session.query(func.avg(EnergyRecord.electricity_consumption_kwh)).scalar() or 0.0

    # Total system consumption
    total_system_kwh = db.session.query(func.sum(EnergyRecord.electricity_consumption_kwh)).scalar() or 0.0

    # Active ANN Model Metrics
    latest_metrics = get_latest_model_metrics()

    # Identify high-consumption users (users with average consumption > moderate threshold)
    low_th, mod_th = get_system_thresholds()
    user_avg_query = db.session.query(
        User.id,
        User.full_name,
        User.email,
        func.avg(EnergyRecord.electricity_consumption_kwh).label('avg_kwh'),
        func.count(EnergyRecord.id).label('rec_count')
    ).join(EnergyRecord, User.id == EnergyRecord.user_id)\
     .group_by(User.id, User.full_name, User.email)\
     .having(func.avg(EnergyRecord.electricity_consumption_kwh) > mod_th)\
     .order_by(func.avg(EnergyRecord.electricity_consumption_kwh).desc())\
     .limit(5).all()

    # Recent System Activities
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()

    # Chart Data: Daily aggregate across all users for last 14 days
    daily_aggregates = db.session.query(
        EnergyRecord.date,
        func.sum(EnergyRecord.electricity_consumption_kwh).label('total_kwh'),
        func.avg(EnergyRecord.electricity_consumption_kwh).label('avg_kwh')
    ).group_by(EnergyRecord.date).order_by(EnergyRecord.date.desc()).limit(14).all()
    
    daily_aggregates.reverse()
    chart_dates = [r.date.strftime('%b %d') for r in daily_aggregates]
    chart_totals = [round(r.total_kwh, 2) for r in daily_aggregates]
    chart_averages = [round(r.avg_kwh, 2) for r in daily_aggregates]

    return render_template(
        'dashboard/admin.html',
        total_users=total_users,
        total_residents=total_residents,
        total_records=total_records,
        total_predictions=total_predictions,
        avg_system_kwh=round(avg_system_kwh, 2),
        total_system_kwh=round(total_system_kwh, 2),
        latest_metrics=latest_metrics,
        high_consumption_users=user_avg_query,
        recent_activities=recent_activities,
        chart_dates=chart_dates,
        chart_totals=chart_totals,
        chart_averages=chart_averages
    )


@admin_bp.route('/ann-training', methods=['GET', 'POST'])
@admin_required
def ann_training():
    """ANN Model Training, Evaluation Metrics, and Training Management."""
    total_records = EnergyRecord.query.count()
    latest_metrics = get_latest_model_metrics()
    all_models = ANNModel.query.order_by(ANNModel.training_date.desc()).all()

    if request.method == 'POST':
        # Trigger training pipeline
        result = train_ann_model(user_id=current_user.id)
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'warning')
        return redirect(url_for('admin.ann_training'))

    return render_template(
        'admin/ann_training.html',
        total_records=total_records,
        latest_metrics=latest_metrics,
        all_models=all_models
    )


@admin_bp.route('/users')
@admin_required
def users():
    """User Management."""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
@admin_required
def toggle_user_role(user_id):
    """Toggle a user's role between admin and resident."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot change your own role.', 'warning')
        return redirect(url_for('admin.users'))

    user.role = 'admin' if user.role == 'resident' else 'resident'
    db.session.commit()
    log_activity(current_user.id, 'CHANGE_ROLE', f"Changed role of user {user.email} to {user.role.upper()}.")
    flash(f"User {user.full_name}'s role changed to {user.role.capitalize()}.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user account."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))

    email = user.email
    db.session.delete(user)
    db.session.commit()
    log_activity(current_user.id, 'DELETE_USER', f"Deleted user {email}.")
    flash(f"User {email} has been permanently deleted.", 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/activity-logs')
@admin_required
def activity_logs():
    """System Audit Trail and Activity Logs."""
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action')

    query = ActivityLog.query
    if action_filter:
        query = query.filter_by(action=action_filter.upper())

    pagination = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        'admin/activity_logs.html',
        logs=pagination.items,
        pagination=pagination,
        action_filter=action_filter
    )


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """System Configuration & Tariff Settings."""
    tariff_setting = SystemSetting.query.filter_by(key='tariff_per_kwh').first()
    low_th_setting = SystemSetting.query.filter_by(key='low_consumption_threshold').first()
    mod_th_setting = SystemSetting.query.filter_by(key='moderate_consumption_threshold').first()

    form = SystemSettingsForm()

    if request.method == 'GET':
        form.tariff_per_kwh.data = float(tariff_setting.value) if tariff_setting else current_app.config.get('DEFAULT_TARIFF_PER_KWH', 120.0)
        form.low_consumption_threshold.data = float(low_th_setting.value) if low_th_setting else current_app.config.get('LOW_CONSUMPTION_THRESHOLD', 5.0)
        form.moderate_consumption_threshold.data = float(mod_th_setting.value) if mod_th_setting else current_app.config.get('MODERATE_CONSUMPTION_THRESHOLD', 10.0)

    if form.validate_on_submit():
        # Update or create tariff
        if not tariff_setting:
            tariff_setting = SystemSetting(key='tariff_per_kwh', value=str(form.tariff_per_kwh.data), description='Electricity tariff rate in Naira per kWh')
            db.session.add(tariff_setting)
        else:
            tariff_setting.value = str(form.tariff_per_kwh.data)

        # Update or create low threshold
        if not low_th_setting:
            low_th_setting = SystemSetting(key='low_consumption_threshold', value=str(form.low_consumption_threshold.data), description='Threshold in kWh for Low consumption tier')
            db.session.add(low_th_setting)
        else:
            low_th_setting.value = str(form.low_consumption_threshold.data)

        # Update or create moderate threshold
        if not mod_th_setting:
            mod_th_setting = SystemSetting(key='moderate_consumption_threshold', value=str(form.moderate_consumption_threshold.data), description='Threshold in kWh for Moderate consumption tier')
            db.session.add(mod_th_setting)
        else:
            mod_th_setting.value = str(form.moderate_consumption_threshold.data)

        db.session.commit()
        log_activity(current_user.id, 'UPDATE_SETTINGS', f"Updated tariff to ₦{form.tariff_per_kwh.data}/kWh and thresholds (Low: {form.low_consumption_threshold.data} kWh, Mod: {form.moderate_consumption_threshold.data} kWh).")
        flash('System settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))

    # Also list manageable recommendations
    custom_recommendations = Recommendation.query.order_by(Recommendation.created_at.desc()).all()
    rec_form = RecommendationForm()

    return render_template(
        'admin/settings.html',
        form=form,
        rec_form=rec_form,
        recommendations=custom_recommendations
    )


@admin_bp.route('/recommendations/add', methods=['POST'])
@admin_required
def add_recommendation():
    """Add a custom recommendation rule."""
    form = RecommendationForm()
    if form.validate_on_submit():
        rec = Recommendation(
            title=form.title.data.strip(),
            message=form.message.data.strip(),
            consumption_level=form.consumption_level.data,
            is_active=form.is_active.data
        )
        db.session.add(rec)
        db.session.commit()
        log_activity(current_user.id, 'ADD_RECOMMENDATION', f"Added recommendation: '{rec.title}'")
        flash('Energy recommendation added successfully.', 'success')
    else:
        flash('Invalid recommendation data. Please review the inputs.', 'danger')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/recommendations/<int:rec_id>/delete', methods=['POST'])
@admin_required
def delete_recommendation(rec_id):
    """Delete a recommendation rule."""
    rec = Recommendation.query.get_or_404(rec_id)
    title = rec.title
    db.session.delete(rec)
    db.session.commit()
    log_activity(current_user.id, 'DELETE_RECOMMENDATION', f"Deleted recommendation '{title}'.")
    flash('Recommendation deleted.', 'info')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/landing-editor', methods=['GET', 'POST'])
@admin_required
def landing_page_editor():
    """Administrator interface to customize public landing page text, headlines, and branding."""
    from app.utils.helpers import get_landing_content, set_system_setting

    if request.method == 'POST':
        # Process all landing page form fields
        editable_keys = [
            'brand_name', 'brand_badge', 'hero_badge', 'hero_title', 'hero_subtitle', 'hero_cta_text', 'hero_subtext',
            'feature1_title', 'feature1_desc', 'feature2_title', 'feature2_desc',
            'feature3_title', 'feature3_desc', 'feature4_title', 'feature4_desc',
            'impact_title', 'impact_subtitle',
            'benefit1_title', 'benefit1_desc', 'benefit2_title', 'benefit2_desc',
            'benefit3_title', 'benefit3_desc', 'benefit4_title', 'benefit4_desc',
            'card_title', 'card_stat1_label', 'card_stat1_val', 'card_stat2_label', 'card_stat2_val', 'card_desc'
        ]

        for key in editable_keys:
            val = request.form.get(key)
            if val is not None:
                set_system_setting(key, val.strip(), f"Landing Page Content: {key}")

        log_activity(current_user.id, 'UPDATE_LANDING_PAGE', "Updated public landing page text, branding, and content.")
        flash('Landing page content and branding updated successfully!', 'success')
        return redirect(url_for('admin.landing_page_editor'))

    content = get_landing_content()
    return render_template('admin/landing_editor.html', content=content)
