# Gunicorn configuration file
import multiprocessing
import logging

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048
reuse_port = True

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 300  # Increase timeout to 5 minutes
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'gunicorn_pdf_translator'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Preload application code before worker processes are forked
preload_app = True

# SSL
keyfile = None
certfile = None

# Print configuration on startup
def on_starting(server):
    logger = logging.getLogger('gunicorn.error')
    logger.info(f'Starting with timeout set to {timeout} seconds')
    logger.info(f'Worker class: {worker_class}')
    logger.info(f'Number of workers: {workers}')