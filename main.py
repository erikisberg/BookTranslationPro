from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

# For production with Gunicorn, use:
# gunicorn -c gunicorn_config.py --reuse-port --reload app:app
# 
# Or set environment variables:
# export GUNICORN_CMD_ARGS="-c gunicorn_config.py --reuse-port --reload"