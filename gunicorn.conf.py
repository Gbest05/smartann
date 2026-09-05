import os

# Gunicorn configuration for Render deployment
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

workers = int(os.environ.get("WEB_CONCURRENCY", 1))
threads = int(os.environ.get("PYTHON_THREADS", 2))
timeout = 120
keepalive = 5

# Stream logs to stdout and stderr so Render shows them in real time
accesslog = "-"
errorlog = "-"
loglevel = "info"
