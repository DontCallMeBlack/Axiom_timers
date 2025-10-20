from pymongo import MongoClient
from datetime import datetime, timedelta
import os

# MongoDB setup
MONGO_URI = "mongodb+srv://dcmbch7:Suppmain123@cluster0.vrweuzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Boss data
BOSSES = [
    {'name': '170', 'respawn_minutes': 80, 'window_minutes': 5},
    {'name': '180', 'respawn_minutes': 90, 'window_minutes': 5},
    {'name': 'Mordy', 'respawn_minutes': 1200, 'window_minutes': 960},
    {'name': 'Hrung', 'respawn_minutes': 1320, 'window_minutes': 1080},
    {'name': '210', 'respawn_minutes': 130, 'window_minutes': 5},
    {'name': '215', 'respawn_minutes': 135, 'window_minutes': 5},
    {'name': 'Proteus', 'respawn_minutes': 1080, 'window_minutes': 15},
    {'name': 'Dino', 'respawn_minutes': 2040, 'window_minutes': 1640},
    {'name': 'Bloodthorn', 'respawn_minutes': 2040, 'window_minutes': 1640},
    {'name': 'Gelebron', 'respawn_minutes': 2040, 'window_minutes': 1640},
    {'name': 'Crom', 'respawn_minutes': 5760, 'window_minutes': 1440}
]

def get_boss_by_name(name):
    for boss in BOSSES:
        if boss['name'] == name:
            return boss
    return None

def fix_timestamps():
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client['axiom']
        timers_collection = db['timers']
        
        print("Connected to MongoDB successfully")
        
        # Get all timers
        all_timers = list(timers_collection.find())
        print(f"Found {len(all_timers)} boss timers")
        
        for timer in all_timers:
            boss_name = timer.get('name')
            boss_info = get_boss_by_name(boss_name)
            
            if not boss_info:
                print(f"Warning: Boss {boss_name} not found in BOSSES list")
                continue
                
            print(f"\nChecking timer for {boss_name}:")
            print("Current values:")
            print(f"kill_time: {timer.get('kill_time', 'Not set')}")
            print(f"spawn_time: {timer.get('spawn_time', 'Not set')}")
            print(f"window_end_time: {timer.get('window_end_time', 'Not set')}")
            
            # Check if kill_time exists and is valid
            try:
                kill_time = datetime.fromisoformat(timer.get('kill_time', ''))
                # If kill_time is valid, recalculate spawn and window times
                spawn_time = kill_time + timedelta(minutes=boss_info['respawn_minutes'])
                window_end_time = spawn_time + timedelta(minutes=boss_info['window_minutes'])
                
                # Update the timer with correct format
                update_data = {
                    'kill_time': kill_time.isoformat(),
                    'spawn_time': spawn_time.isoformat(),
                    'window_end_time': window_end_time.isoformat()
                }
                
                timers_collection.update_one(
                    {'name': boss_name},
                    {'$set': update_data}
                )
                
                print("\nUpdated values:")
                print(f"kill_time: {update_data['kill_time']}")
                print(f"spawn_time: {update_data['spawn_time']}")
                print(f"window_end_time: {update_data['window_end_time']}")
                
            except (ValueError, TypeError) as e:
                print(f"Error with {boss_name} timer: {str(e)}")
                continue
            
        print("\nTimestamp update complete!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_timestamps()