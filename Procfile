api:       uvicorn app.main:app --host 0.0.0.0 --port 8000
dashboard: gunicorn -w 2 -b 0.0.0.0:5000 "dashboard:create_dashboard()"
