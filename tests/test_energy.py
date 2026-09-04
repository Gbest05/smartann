import io
import unittest
from datetime import date, timedelta
from app import create_app
from app.models import db, User, EnergyRecord, SystemSetting


class EnergyTestCase(unittest.TestCase):
    """Test suite for energy records CRUD, cost calculation, and CSV import."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Seed test user and admin
        self.admin = User(full_name='Admin Test', email='admin@test.com', role='admin')
        self.admin.set_password('AdminPass123!')
        
        self.resident = User(full_name='Resident Test', email='resident@test.com', role='resident')
        self.resident.set_password('ResidentPass123!')

        db.session.add_all([self.admin, self.resident])
        
        # System settings
        db.session.add(SystemSetting(key='tariff_per_kwh', value='120.0', description='Tariff'))
        db.session.add(SystemSetting(key='low_consumption_threshold', value='5.0', description='Low'))
        db.session.add(SystemSetting(key='moderate_consumption_threshold', value='10.0', description='Mod'))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

    def test_add_energy_record(self):
        """Test manually adding an energy consumption record."""
        self.login('resident@test.com', 'ResidentPass123!')
        response = self.client.post('/energy/add', data={
            'date': '2026-08-15',
            'electricity_consumption_kwh': '8.5',
            'peak_consumption_kwh': '5.0',
            'off_peak_consumption_kwh': '3.5',
            'appliance_usage_hours': '8.0',
            'estimated_cost': ''  # auto-calculated
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        record = EnergyRecord.query.filter_by(user_id=self.resident.id).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.electricity_consumption_kwh, 8.5)
        self.assertEqual(record.estimated_cost, 1020.0)  # 8.5 * 120.0
        self.assertEqual(record.consumption_level, 'Moderate')

    def test_edit_energy_record(self):
        """Test updating an existing energy record."""
        rec = EnergyRecord(
            user_id=self.resident.id,
            date=date.today(),
            electricity_consumption_kwh=6.0,
            peak_consumption_kwh=3.5,
            off_peak_consumption_kwh=2.5,
            appliance_usage_hours=6.0,
            estimated_cost=720.0
        )
        db.session.add(rec)
        db.session.commit()

        self.login('resident@test.com', 'ResidentPass123!')
        response = self.client.post(f'/energy/edit/{rec.id}', data={
            'date': str(date.today()),
            'electricity_consumption_kwh': '4.5',
            'peak_consumption_kwh': '2.5',
            'off_peak_consumption_kwh': '2.0',
            'appliance_usage_hours': '5.0',
            'estimated_cost': ''
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        updated = EnergyRecord.query.get(rec.id)
        self.assertEqual(updated.electricity_consumption_kwh, 4.5)
        self.assertEqual(updated.consumption_level, 'Low')

    def test_delete_energy_record(self):
        """Test deleting an energy record."""
        rec = EnergyRecord(
            user_id=self.resident.id,
            date=date.today(),
            electricity_consumption_kwh=10.0,
            estimated_cost=1200.0
        )
        db.session.add(rec)
        db.session.commit()

        self.login('resident@test.com', 'ResidentPass123!')
        response = self.client.post(f'/energy/delete/{rec.id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(EnergyRecord.query.get(rec.id))

    def test_csv_import(self):
        """Test administrator batch CSV import."""
        self.login('admin@test.com', 'AdminPass123!')

        csv_content = """date,electricity_consumption_kwh,peak_consumption_kwh,off_peak_consumption_kwh,appliance_usage_hours,estimated_cost
2026-08-01,8.5,5.0,3.5,8.0,1020.0
2026-08-02,9.0,5.5,3.5,8.5,1080.0
2026-08-03,4.0,2.0,2.0,4.0,480.0"""

        data = {
            'user_id': self.resident.id,
            'is_synthetic': False,
            'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'test_energy.csv')
        }

        response = self.client.post('/energy/import-csv', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EnergyRecord.query.filter_by(user_id=self.resident.id).count(), 3)


if __name__ == '__main__':
    unittest.main()
