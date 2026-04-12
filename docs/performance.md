# Performance

Location:
- locust/locustfile.py

Run (headless example):
- python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
- python -m locust -f locust/locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 20s --only-summary
