from pymongo import MongoClient
import os
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
MONGO_URI = "mongodb+srv://dcmbch7:Suppmain123@cluster0.vrweuzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def test_connection():
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test the connection
        client.admin.command('ping')
        logger.info("MongoDB connection test successful")
        
        # Get the database
        db = client['axiom']
        timers_collection = db['timers']
        
        # Try to read Mordy's data
        mordy = timers_collection.find_one({'name': 'Mordy'})
        if mordy:
            logger.info("\nMordy's data found:")
            for key, value in mordy.items():
                if key != '_id':
                    logger.info(f"{key}: {value}")
            
            # Try to parse the timestamps
            if 'kill_time' in mordy:
                try:
                    kill_dt = datetime.fromisoformat(mordy['kill_time'])
                    logger.info(f"\nParsed kill_time: {kill_dt}")
                except ValueError as e:
                    logger.error(f"Error parsing kill_time: {e}")
            
            # Calculate remaining time
            now = datetime.utcnow()
            if 'spawn_time' in mordy:
                spawn_dt = datetime.fromisoformat(mordy['spawn_time'])
                remaining = spawn_dt - now
                logger.info(f"Current time (UTC): {now}")
                logger.info(f"Time until spawn: {remaining}")
        else:
            logger.warning("No data found for Mordy")
            
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    test_connection()