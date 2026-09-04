import unittest
from datetime import date, timedelta
from app import create_app
from app.models import db, User, EnergyRecord, ANNModel, SystemSetting
from app.ml.preprocessing import prepare_training_data, prepare_single_inference_vector, extract_date_features
from app.ml.train_model import train_ann_model, get_latest_model_metrics
from app.ml.predict import predict_energy_consumption
from app.utils.recommendations import get_recommendations_for_user


class ANNModelTestCase(unittest.TestCase):
    """Test suite for the Scikit-learn Artificial Neural Network (MLPRegressor) engine."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user
        self.user = User(full_name='ANN Tester', email='ann@test.com', role='resident')
        self.user.set_password('Password123!')
        db.session.add(self.user)

        # Settings
        db.session.add(SystemSetting(key='tariff_per_kwh', value='120.0', description='Tariff'))
        db.session.add(SystemSetting(key='low_consumption_threshold', value='5.0', description='Low'))
        db.session.add(SystemSetting(key='moderate_consumption_threshold', value='10.0', description='Mod'))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_feature_extraction(self):
        """Test temporal and calendar feature extraction."""
        dt = date(2026, 8, 15)  # Saturday
        feats = extract_date_features(dt)
        self.assertEqual(feats['day'], 15)
        self.assertEqual(feats['month'], 8)
        self.assertEqual(feats['day_of_week'], 5)
        self.assertEqual(feats['is_weekend'], 1)

    def test_insufficient_data_handling(self):
        """Verify ANN model gracefully refuses training when dataset is too small (<15 records)."""
        # Add only 3 records
        for i in range(3):
            rec = EnergyRecord(
                user_id=self.user.id,
                date=date.today() - timedelta(days=i),
                electricity_consumption_kwh=8.0,
                peak_consumption_kwh=4.5,
                off_peak_consumption_kwh=3.5,
                appliance_usage_hours=8.0,
                estimated_cost=960.0
            )
            db.session.add(rec)
        db.session.commit()

        result = train_ann_model()
        self.assertFalse(result['success'])
        self.assertIn('Insufficient dataset size', result['message'])

    def test_ann_training_and_evaluation(self):
        """Verify MLPRegressor training pipeline, metrics calculation, and database persistence."""
        # Seed 30 synthetic records for reliable training
        records = []
        start_date = date.today() - timedelta(days=30)
        for i in range(30):
            kwh = 7.0 + (i % 5) * 0.8
            rec = EnergyRecord(
                user_id=self.user.id,
                date=start_date + timedelta(days=i),
                electricity_consumption_kwh=kwh,
                peak_consumption_kwh=round(kwh * 0.6, 2),
                off_peak_consumption_kwh=round(kwh * 0.4, 2),
                appliance_usage_hours=round(kwh * 0.9, 1),
                estimated_cost=round(kwh * 120.0, 2)
            )
            records.append(rec)
        db.session.bulk_save_objects(records)
        db.session.commit()

        result = train_ann_model()
        self.assertTrue(result['success'])
        self.assertIn('mae', result)
        self.assertIn('mse', result)
        self.assertIn('rmse', result)
        self.assertIn('r2_score', result)
        self.assertGreater(result['training_records'], 0)
        self.assertGreater(result['test_records'], 0)

        # Check DB model record
        active_model = ANNModel.query.filter_by(status='Active').first()
        self.assertIsNotNone(active_model)
        self.assertEqual(active_model.status, 'Active')

    def test_prediction_inference(self):
        """Test energy consumption prediction with cost calculation."""
        pred = predict_energy_consumption(
            target_date=date.today(),
            appliance_usage_hours=8.0,
            peak_consumption_kwh=5.0,
            off_peak_consumption_kwh=3.5
        )
        self.assertIn('predicted_consumption_kwh', pred)
        self.assertIn('estimated_cost', pred)
        self.assertIn('consumption_level', pred)
        self.assertGreater(pred['predicted_consumption_kwh'], 0)
        self.assertGreater(pred['estimated_cost'], 0)

    def test_dynamic_recommendations(self):
        """Test recommendation generator for low, moderate, and high tiers."""
        low_recs = get_recommendations_for_user(current_kwh=3.5)
        self.assertEqual(low_recs['level'], 'Low')
        self.assertGreater(len(low_recs['recommendations']), 0)

        mod_recs = get_recommendations_for_user(current_kwh=7.5)
        self.assertEqual(mod_recs['level'], 'Moderate')

        high_recs = get_recommendations_for_user(current_kwh=14.0)
        self.assertEqual(high_recs['level'], 'High')


if __name__ == '__main__':
    unittest.main()
