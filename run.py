import logging
from logging.handlers import RotatingFileHandler
from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Set up logging configuration
    log_level = logging.DEBUG if app.config.get("DEBUG", False) else logging.INFO
    logging.basicConfig(level=log_level)
    
    # Rotating log handler for log file
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(log_level)
    app.logger.addHandler(file_handler)

    logging.info("Flask app started")
    app.run(host="0.0.0.0", port=8000)
