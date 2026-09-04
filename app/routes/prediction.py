from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, Prediction, EnergyRecord
from app.forms import PredictionForm
from app.ml.predict import predict_energy_consumption
from app.ml.train_model import get_latest_model_metrics
from app.utils.helpers import log_activity, get_active_tariff
from app.utils.recommendations import get_recommendations_for_user

prediction_bp = Blueprint('prediction', __name__, url_prefix='/prediction')


@prediction_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Interactive ANN Energy Prediction page."""
    form = PredictionForm()
    prediction_result = None
    active_tariff = get_active_tariff()
    model_metrics = get_latest_model_metrics()

    # Prepopulate recent baseline if user has records
    user_avg = db.session.query(func.avg(EnergyRecord.electricity_consumption_kwh)).filter_by(user_id=current_user.id).scalar()
    if user_avg and not form.is_submitted():
        form.recent_avg_kwh.data = round(user_avg, 2)

    if form.validate_on_submit():
        target_date = form.prediction_date.data
        appliance_hours = form.appliance_usage_hours.data
        peak_kwh = form.expected_peak_kwh.data or 0.0
        off_peak_kwh = form.expected_off_peak_kwh.data or 0.0
        baseline = form.recent_avg_kwh.data

        # Run ANN model inference
        prediction_result = predict_energy_consumption(
            target_date=target_date,
            appliance_usage_hours=appliance_hours,
            peak_consumption_kwh=peak_kwh,
            off_peak_consumption_kwh=off_peak_kwh,
            recent_baseline=baseline
        )

        # Persist prediction in database
        prediction_entry = Prediction(
            user_id=current_user.id,
            prediction_date=target_date,
            predicted_consumption_kwh=prediction_result['predicted_consumption_kwh'],
            estimated_cost=prediction_result['estimated_cost'],
            peak_consumption_kwh=peak_kwh,
            off_peak_consumption_kwh=off_peak_kwh,
            appliance_usage_hours=appliance_hours,
            consumption_level=prediction_result['consumption_level'],
            model_version=prediction_result['model_version']
        )
        db.session.add(prediction_entry)
        db.session.commit()

        # Audit log
        log_activity(
            current_user.id,
            'PREDICT_ENERGY',
            f"Generated ANN prediction for {target_date}: {prediction_result['predicted_consumption_kwh']} kWh (₦{prediction_result['estimated_cost']:,.2f})."
        )

        flash(f"Energy prediction generated successfully for {target_date.strftime('%B %d, %Y')}!", 'success')

        # Get relevant recommendations based on predicted consumption
        recs = get_recommendations_for_user(current_kwh=prediction_result['predicted_consumption_kwh'])
        prediction_result['recommendations'] = recs['recommendations'][:3]

    # Retrieve past 5 predictions for quick reference
    recent_predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.created_at.desc()).limit(5).all()

    return render_template(
        'prediction/index.html',
        form=form,
        prediction_result=prediction_result,
        recent_predictions=recent_predictions,
        model_metrics=model_metrics,
        tariff=active_tariff
    )


@prediction_bp.route('/history')
@login_required
def history():
    """View chronological history of ANN predictions."""
    page = request.args.get('page', 1, type=int)
    per_page = 15

    if current_user.is_admin:
        query = Prediction.query
    else:
        query = Prediction.query.filter_by(user_id=current_user.id)

    pagination = query.order_by(Prediction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        'prediction/history.html',
        predictions=pagination.items,
        pagination=pagination
    )


@prediction_bp.route('/delete/<int:pred_id>', methods=['POST'])
@login_required
def delete_prediction(pred_id):
    """Delete a prediction record."""
    pred = Prediction.query.get_or_404(pred_id)

    if not current_user.is_admin and pred.user_id != current_user.id:
        flash('Unauthorized to delete this prediction.', 'danger')
        return redirect(url_for('prediction.history'))

    db.session.delete(pred)
    db.session.commit()

    log_activity(current_user.id, 'DELETE_PREDICTION', f"Deleted prediction #{pred_id}.")
    flash('Prediction entry removed.', 'info')
    return redirect(url_for('prediction.history'))
