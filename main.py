# # main.py
# import logging
# from app import create_app
# from config import LOG_LEVEL, LOG_FORMAT
# import os
# from dotenv import load_dotenv
from app import create_app, logger  # Use the logger from the app module
from models import db
# logging.basicConfig(
#     level=getattr(logging, LOG_LEVEL, logging.INFO),
#     format=LOG_FORMAT,
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler("logs/medmatchint.log", mode="a", encoding="utf-8")
#     ]
# )

# logger = logging.getLogger()
# logger.setLevel(logging.INFO)

# app = create_app()

# with app.app_context():
#     from models import db
#     logger.info("🔧 Ensuring database schema is ready...")
#     db.create_all()  # Ensure tables exist
#     logger.info("✅ Database schema is ready.")

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=False)

    # main.py
import logging
from app import create_app, db
from config import LOG_LEVEL, LOG_FORMAT
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Centralized Logging Setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/medmatchint.log", mode="a", encoding="utf-8")
    ]
)

logger = logging.getLogger("medmatchint")
logger.setLevel(logging.INFO)

# Create the Flask app using the factory pattern
app = create_app()

with app.app_context():
    logger.info("🔧 Ensuring database schema is ready...")
    
    try:
        # Initialize the database schema within the app context
        db.create_all()  
        logger.info("✅ Database schema is ready.")
    except Exception as e:
        logger.error(f"❌ Error ensuring database schema: {str(e)}")

# Running the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)