import os
from app import create_app, init_db_and_defaults

# Application instance for WSGI servers running `gunicorn app:app`
env = os.environ.get('FLASK_ENV', 'production')
app = create_app(env)

# Ensure database tables and essential default settings/accounts exist
init_db_and_defaults(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
