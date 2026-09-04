import joblib
from pathlib import Path
from flask import current_app
from app.ml.preprocessing import prepare_single_inference_vector
from app.utils.helpers import calculate_cost, classify_consumption, get_active_tariff


def predict_energy_consumption(
    target_date,
    appliance_usage_hours: float,
    peak_consumption_kwh: float = 0.0,
    off_peak_consumption_kwh: float = 0.0,
    recent_baseline: float = None
) -> dict:
    """
    Run ANN model inference to predict future residential electricity consumption.
    
    Returns:
        dict: Predicted kWh, estimated cost (₦), classification tier, model version, and status.
    """
    model_dir = Path(current_app.config.get('ML_MODEL_DIR', Path(__file__).parent / 'models'))
    model_filepath = model_dir / 'ann_energy_model.joblib'

    tariff = get_active_tariff()
    is_ann_model = False
    model_version = "ANN (MLPRegressor v1.0)"

    # Prepare single inference feature DataFrame
    input_df = prepare_single_inference_vector(
        target_date=target_date,
        appliance_hours=appliance_usage_hours,
        peak_kwh=peak_consumption_kwh,
        off_peak_kwh=off_peak_consumption_kwh,
        recent_baseline=recent_baseline
    )

    if model_filepath.exists():
        try:
            bundle = joblib.load(model_filepath)
            mlp_model = bundle['model']
            scaler = bundle['scaler']

            # Scale features
            input_scaled = scaler.transform(input_df)

            # Predict using ANN
            raw_pred = mlp_model.predict(input_scaled)[0]
            # Ensure predicted energy is positive and realistic
            pred_kwh = max(0.5, round(float(raw_pred), 2))
            is_ann_model = True
            model_version = f"Trained ANN ({bundle.get('trained_at', 'Active')[:10]})"
        except Exception as e:
            current_app.logger.warning(f"Error loading trained ANN model: {e}. Using calibrated fallback heuristic.")
            pred_kwh = _heuristic_prediction(peak_consumption_kwh, off_peak_consumption_kwh, appliance_usage_hours, recent_baseline)
            model_version = "Calibrated Baseline Heuristic (Model Load Error)"
    else:
        # Fallback when no trained model exists yet
        pred_kwh = _heuristic_prediction(peak_consumption_kwh, off_peak_consumption_kwh, appliance_usage_hours, recent_baseline)
        model_version = "Calibrated Baseline Heuristic (Model Untrained)"

    estimated_cost = calculate_cost(pred_kwh, tariff)
    tier = classify_consumption(pred_kwh)

    return {
        'predicted_consumption_kwh': pred_kwh,
        'estimated_cost': estimated_cost,
        'consumption_level': tier,
        'tariff_rate': tariff,
        'model_version': model_version,
        'is_ann_model': is_ann_model,
        'appliance_usage_hours': appliance_usage_hours,
        'peak_consumption_kwh': peak_consumption_kwh,
        'off_peak_consumption_kwh': off_peak_consumption_kwh,
        'target_date': str(target_date)
    }


def _heuristic_prediction(peak_kwh: float, off_peak_kwh: float, appliance_hours: float, baseline: float = None) -> float:
    """Calibrated physical estimation fallback when ANN model has not been trained yet."""
    if peak_kwh > 0 or off_peak_kwh > 0:
        base = (peak_kwh * 0.95) + (off_peak_kwh * 0.95) + (appliance_hours * 0.25)
    elif baseline and baseline > 0:
        base = (baseline * 0.85) + (appliance_hours * 0.3)
    else:
        base = max(1.5, appliance_hours * 1.15)
    return max(0.5, round(base, 2))
