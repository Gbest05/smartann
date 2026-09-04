import unittest
from app import create_app
from app.models import db, User


class AuthTestCase(unittest.TestCase):
    """Test suite for authentication, registration, password hashing, and role checks."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        """Verify secure password hashing and verification."""
        u = User(full_name='Test User', email='test@example.com', role='resident')
        u.set_password('SecretPassword123')
        self.assertFalse(u.password_hash == 'SecretPassword123')
        self.assertTrue(u.check_password('SecretPassword123'))
        self.assertFalse(u.check_password('WrongPassword'))

    def test_user_registration(self):
        """Test new user registration."""
        response = self.client.post('/auth/register', data={
            'full_name': 'New Resident',
            'email': 'newresident@example.com',
            'password': 'Password123!',
            'password2': 'Password123!',
            'role': 'resident'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(email='newresident@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, 'New Resident')
        self.assertEqual(user.role, 'resident')

    def test_duplicate_email_registration(self):
        """Test registration rejection on duplicate email address."""
        u = User(full_name='Existing User', email='duplicate@example.com', role='resident')
        u.set_password('Password123!')
        db.session.add(u)
        db.session.commit()

        response = self.client.post('/auth/register', data={
            'full_name': 'Another User',
            'email': 'duplicate@example.com',
            'password': 'Password123!',
            'password2': 'Password123!',
            'role': 'resident'
        }, follow_redirects=True)
        self.assertIn(b'already exists', response.data)

    def test_user_login_and_logout(self):
        """Test valid login credentials and logout session termination."""
        u = User(full_name='Login Tester', email='login@example.com', role='resident')
        u.set_password('CorrectPassword!')
        db.session.add(u)
        db.session.commit()

        # Valid login
        response = self.client.post('/auth/login', data={
            'email': 'login@example.com',
            'password': 'CorrectPassword!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back', response.data)

        # Logout
        response = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'logged out', response.data)

    def test_invalid_login(self):
        """Test invalid credentials error handling."""
        response = self.client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'BadPassword'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid email address or password', response.data)


if __name__ == '__main__':
    unittest.main()
