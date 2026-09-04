import os
import joblib
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from flask import current_app
from app.models import db, ANNModel
from app.ml.preprocessing import prepare_training_data, FEATURE_COLUMNS
from app.utils.helpers import log_activity


def get_model_file_path() -> Path:
    """Get the target filepath for the serialized ANN model artifact."""
    model_dir = Path(current_app.config.get('ML_MODEL_DIR', Path(__file__).parent / 'models'))
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / 'ann_energy_model.joblib'


def train_ann_model(user_id: int = None) -> dict:
    """
    Train the Artificial Neural Network (MLPRegressor) on historical energy data.
    
    Returns:
        dict: Training status, dataset sizes, and performance metrics (MAE, MSE, RMSE, R2).
    """
    X, y, total_records = prepare_training_data()

    # Minimum data validation
    MIN_REQUIRED_RECORDS = 15
    if total_records < MIN_REQUIRED_RECORDS:
        return {
            'success': False,
            'message': f"Insufficient dataset size. Found {total_records} energy records, but at least {MIN_REQUIRED_RECORDS} records are required to train the Artificial Neural Network model effectively.",
            'total_records': total_records
        }

    try:
        # Split dataset into training and testing sets (80% Train, 20% Test)
        test_size = 0.2 if total_records >= 20 else 0.15
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, shuffle=True
        )

        # Feature scaling using StandardScaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Artificial Neural Network Architecture (Multi-Layer Perceptron)
        # 2 hidden layers: Layer 1 = 64 neurons, Layer 2 = 32 neurons
        # Activation function: ReLU (Rectified Linear Unit)
        # Optimizer: Adam (Adaptive Moment Estimation)
        mlp = MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation='relu',
            solver='adam',
            max_iter=1000,
            alpha=0.0001,
            batch_size='auto',
            learning_rate_init=0.01,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=25,
            random_state=42
        )

        # Fit the ANN
        mlp.fit(X_train_scaled, y_train)

        # Model evaluation on held-out test data
        y_pred = mlp.predict(X_test_scaled)
        
        # Calculate Regression Metrics
        mae = float(mean_absolute_error(y_test, y_pred))
        mse = float(mean_squared_error(y_test, y_pred))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_test, y_pred))

        # Bundle model, scaler, metadata
        model_filepath = get_model_file_path()
        model_payload = {
            'model': mlp,
            'scaler': scaler,
            'feature_names': FEATURE_COLUMNS,
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'train_size': len(X_train),
            'test_size': len(X_test),
            'metrics': {
                'mae': round(mae, 4),
                'mse': round(mse, 4),
                'rmse': round(rmse, 4),
                'r2_score': round(r2, 4)
            }
        }

        # Save model to disk using Joblib
        joblib.dump(model_payload, model_filepath)

        # Archive prior active models in database
        ANNModel.query.filter_by(status='Active').update({'status': 'Archived'})

        # Save new model metadata in database
        model_record = ANNModel(
            model_name=f"ANN-MLPRegressor-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            training_date=datetime.now(timezone.utc),
            training_records=len(X_train),
            test_records=len(X_test),
            mae=mae,
            mse=mse,
            rmse=rmse,
            r2_score=r2,
            model_file=str(model_filepath.name),
            status='Active',
            notes=f"Trained on {total_records} historical consumption records. Hidden layers: (64, 32), Activation: ReLU, Optimizer: Adam."
        )
        db.session.add(model_record)
        db.session.commit()

        # Audit activity
        log_activity(
            user_id=user_id,
            action='TRAIN_ANN_MODEL',
            description=f"Trained ANN model '{model_record.model_name}' on {total_records} records. R²: {r2:.4f}, MAE: {mae:.4f} kWh."
        )

        return {
            'success': True,
            'model_name': model_record.model_name,
            'training_records': len(X_train),
            'test_records': len(X_test),
            'total_records': total_records,
            'mae': round(mae, 4),
            'mse': round(mse, 4),
            'rmse': round(rmse, 4),
            'r2_score': round(r2, 4),
            'message': f"Artificial Neural Network model successfully trained and evaluated! Achieved R² Score of {r2:.4f} and MAE of {mae:.4f} kWh."
        }

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"ANN Model Training Failed: {str(e)}")
        return {
            'success': False,
            'message': f"Training failed due to error: {str(e)}",
            'total_records': total_records
        }


def get_latest_model_metrics() -> dict:
    """Retrieve metadata and accuracy metrics of the current active ANN model."""
    active_model = ANNModel.query.filter_by(status='Active').order_by(ANNModel.training_date.desc()).first()
    if active_model:
        return {
            'exists': True,
            'model_name': active_model.model_name,
            'training_date': active_model.training_date.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'training_records': active_model.training_records,
            'test_records': active_model.test_records,
            'mae': round(active_model.mae, 4),
            'mse': round(active_model.mse, 4),
            'rmse': round(active_model.rmse, 4),
            'r2_score': round(active_model.r2_score, 4),
            'status': active_model.status,
            'notes': active_model.notes
        }
    return {
        'exists': False,
        'model_name': 'No Active Model',
        'training_date': 'N/A',
        'training_records': 0,
        'test_records': 0,
        'mae': 0.0,
        'mse': 0.0,
        'rmse': 0.0,
        'r2_score': 0.0,
        'status': 'Not Trained',
        'notes': 'ANN model has not been trained yet. Train the model using historical records.'
    }
