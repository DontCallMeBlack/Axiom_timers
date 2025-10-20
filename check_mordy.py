from pymongo import MongoClient
from datetime import datetime

# MongoDB setup
MONGO_URI = "mongodb+srv://dcmbch7:Suppmain123@cluster0.vrweuzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def check_mordy_timer():
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client['axiom']
        timers_collection = db['timers']
        
        # Get Mordy's timer
        mordy = timers_collection.find_one({'name': 'Mordy'})
        
        if mordy:
            print("\nMordy's timer data in database:")
            for key, value in mordy.items():
                print(f"{key}: {value}")
            
            # Try to parse the timestamps
            if 'kill_time' in mordy:
                try:
                    kill_dt = datetime.fromisoformat(mordy['kill_time'])
                    print(f"\nParsed kill_time: {kill_dt}")
                except ValueError as e:
                    print(f"\nError parsing kill_time: {e}")
            
            if 'spawn_time' in mordy:
                try:
                    spawn_dt = datetime.fromisoformat(mordy['spawn_time'])
                    print(f"Parsed spawn_time: {spawn_dt}")
                except ValueError as e:
                    print(f"Error parsing spawn_time: {e}")
            
            if 'window_end_time' in mordy:
                try:
                    window_dt = datetime.fromisoformat(mordy['window_end_time'])
                    print(f"Parsed window_end_time: {window_dt}")
                except ValueError as e:
                    print(f"Error parsing window_end_time: {e}")
                    
            # Calculate remaining times
            now = datetime.utcnow()
            print(f"\nCurrent time (UTC): {now}")
            
            if 'spawn_time' in mordy:
                spawn_dt = datetime.fromisoformat(mordy['spawn_time'])
                remaining = spawn_dt - now
                print(f"Time until spawn: {remaining}")
                
        else:
            print("No timer found for Mordy")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    check_mordy_timer()