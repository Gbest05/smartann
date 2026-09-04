import numpy as np
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Optional
from app.models import EnergyRecord


FEATURE_COLUMNS = [
    'day',
    'month',
    'day_of_week',
    'is_weekend',
    'peak_consumption_kwh',
    'off_peak_consumption_kwh',
    'appliance_usage_hours',
    'lag_1_consumption',
    'rolling_avg_7d'
]


def extract_date_features(dt) -> dict:
    """Extract calendar and cyclic temporal indicators from date/datetime."""
    if isinstance(dt, str):
        dt = datetime.strptime(dt, '%Y-%m-%d').date()
    elif isinstance(dt, datetime):
        dt = dt.date()

    day_of_week = dt.weekday()  # 0=Monday, 6=Sunday
    is_weekend = 1 if day_of_week in [5, 6] else 0

    return {
        'day': dt.day,
        'month': dt.month,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend
    }


def prepare_training_data() -> Tuple[pd.DataFrame, pd.Series, int]:
    """Retrieve historical energy records from database, engineer features, and return X, y."""
    records = EnergyRecord.query.order_by(EnergyRecord.date.asc()).all()
    if not records:
        return pd.DataFrame(), pd.Series(), 0

    data = []
    for r in records:
        data.append({
            'date': r.date,
            'user_id': r.user_id,
            'kwh': r.electricity_consumption_kwh,
            'peak_kwh': r.peak_consumption_kwh,
            'off_peak_kwh': r.off_peak_consumption_kwh,
            'appliance_hours': r.appliance_usage_hours
        })

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['user_id', 'date']).reset_index(drop=True)

    # Date-based features
    df['day'] = df['date'].dt.day
    df['month'] = df['date'].dt.month
    df['day_of_week'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)

    # Operational features
    df['peak_consumption_kwh'] = df['peak_kwh']
    df['off_peak_consumption_kwh'] = df['off_peak_kwh']
    df['appliance_usage_hours'] = df['appliance_hours']

    # Lag and rolling features computed per user where possible
    df['lag_1_consumption'] = df.groupby('user_id')['kwh'].shift(1)
    df['rolling_avg_7d'] = df.groupby('user_id')['kwh'].shift(1).rolling(window=7, min_periods=1).mean()

    # Fill NaN values (e.g. for the first few days of records) with user or global median
    overall_median = df['kwh'].median() if not df.empty else 8.5
    df['lag_1_consumption'] = df['lag_1_consumption'].fillna(df['kwh'])
    df['rolling_avg_7d'] = df['rolling_avg_7d'].fillna(df['kwh'])
    df['lag_1_consumption'] = df['lag_1_consumption'].fillna(overall_median)
    df['rolling_avg_7d'] = df['rolling_avg_7d'].fillna(overall_median)

    X = df[FEATURE_COLUMNS].copy()
    y = df['kwh'].copy()

    return X, y, len(df)


def prepare_single_inference_vector(
    target_date,
    appliance_hours: float,
    peak_kwh: float,
    off_peak_kwh: float,
    recent_baseline: Optional[float] = None
) -> pd.DataFrame:
    """Format single input data row into DataFrame with all expected feature columns for ANN inference."""
    date_feats = extract_date_features(target_date)
    
    # Baseline estimation for lag and rolling averages
    if recent_baseline is None or recent_baseline <= 0:
        recent_baseline = (peak_kwh + off_peak_kwh) if (peak_kwh + off_peak_kwh) > 0 else (appliance_hours * 1.1)

    row = {
        'day': date_feats['day'],
        'month': date_feats['month'],
        'day_of_week': date_feats['day_of_week'],
        'is_weekend': date_feats['is_weekend'],
        'peak_consumption_kwh': float(peak_kwh),
        'off_peak_consumption_kwh': float(off_peak_kwh),
        'appliance_usage_hours': float(appliance_hours),
        'lag_1_consumption': float(recent_baseline),
        'rolling_avg_7d': float(recent_baseline)
    }

    return pd.DataFrame([row], columns=FEATURE_COLUMNS)
