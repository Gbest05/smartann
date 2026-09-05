import os
from app import create_app, _ensure_startup_data

# Determine environment
env = os.environ.get('FLASK_ENV', 'production')
app = create_app(env)

# Ensure database tables and initial defaults exist safely on startup
_ensure_startup_data(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
