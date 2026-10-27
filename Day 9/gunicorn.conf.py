import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
accesslog = "-"
errorlog = "-"
