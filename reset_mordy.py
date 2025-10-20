from pymongo import MongoClient
from datetime import datetime

# MongoDB setup
MONGO_URI = "mongodb+srv://dcmbch7:Suppmain123@cluster0.vrweuzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def reset_mordy():
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client['axiom']
        timers_collection = db['timers']
        
        # Set Mordy's timer data
        timer_data = {
            "name": "Mordy",
            "kill_time": "2025-10-20T15:01:13",
            "spawn_time": "2025-10-21T11:01:13",
            "window_end_time": "2025-10-22T03:01:13",
            "user": "dontcallmeblack"
        }
        
        # Update the timer
        result = timers_collection.update_one(
            {'name': 'Mordy'},
            {'$set': timer_data},
            upsert=True
        )
        
        print("Mordy's timer updated successfully")
        print(f"Modified: {result.modified_count}, Upserted: {result.upserted_id}")
        
        # Verify the data
        mordy = timers_collection.find_one({'name': 'Mordy'})
        print("\nVerified data in database:")
        for key, value in mordy.items():
            if key != '_id':
                print(f"{key}: {value}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    reset_mordy()