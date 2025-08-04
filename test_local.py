#!/usr/bin/env python3
"""
Local test script for Axiom Timer App
Run this to test the app locally without deploying
"""
import os
from datetime import datetime, timedelta
from api.index import app, timers_collection, BOSSES

if __name__ == '__main__':
    # Set environment variables for local testing
    os.environ['SECRET_KEY'] = 'test_secret_key_change_this'
    os.environ['MONGO_URI'] = 'mongodb+srv://dcmbch7:EDxClAIUCaBpcD7z@cluster0.z0dys6f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
    
    print("🎨 Setting up sample timer data for progress bar testing...")
    
    # Sample timers with different time ranges to show all progress bar states
    sample_timers = [
        {
            "name": "170",
            "kill_time": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
            "spawn_time": (datetime.utcnow() + timedelta(minutes=41)).isoformat(),
            "window_end_time": (datetime.utcnow() + timedelta(minutes=46)).isoformat(),
            "user": "TestUser1"
        },
        {
            "name": "180", 
            "kill_time": (datetime.utcnow() - timedelta(minutes=60)).isoformat(),
            "spawn_time": (datetime.utcnow() + timedelta(minutes=26)).isoformat(),
            "window_end_time": (datetime.utcnow() + timedelta(minutes=31)).isoformat(),
            "user": "TestUser2"
        },
        {
            "name": "Mordy",
            "kill_time": (datetime.utcnow() - timedelta(hours=18)).isoformat(),
            "spawn_time": (datetime.utcnow() + timedelta(minutes=120)).isoformat(),
            "window_end_time": (datetime.utcnow() + timedelta(hours=18)).isoformat(),
            "user": "TestUser3"
        },
        {
            "name": "210",
            "kill_time": (datetime.utcnow() - timedelta(minutes=100)).isoformat(),
            "spawn_time": (datetime.utcnow() + timedelta(minutes=23)).isoformat(),
            "window_end_time": (datetime.utcnow() + timedelta(minutes=28)).isoformat(),
            "user": "TestUser4"
        },
        {
            "name": "Proteus",
            "kill_time": (datetime.utcnow() - timedelta(hours=10)).isoformat(),
            "spawn_time": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
            "window_end_time": (datetime.utcnow() + timedelta(minutes=61)).isoformat(),
            "user": "TestUser5"
        }
    ]
    
    # Insert sample data with better error handling
    for timer in sample_timers:
        try:
            result = timers_collection.update_one(
                {'name': timer['name']}, 
                {'$set': timer}, 
                upsert=True
            )
            if result.upserted_id or result.modified_count > 0:
                print(f"✅ Added sample timer for {timer['name']}")
            else:
                print(f"⚠️  Timer for {timer['name']} already exists")
        except Exception as e:
            print(f"❌ Could not add sample timer for {timer['name']}: {e}")
    
    print("🚀 Starting Axiom Timer App locally...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("🔑 Admin users: dontcallmeblack, neveon, windlord, snail, icymagic")
    print("🎨 Sample timers added - you'll see progress bars in action!")
    print("💡 If you don't see progress bars, try resetting a timer manually")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Run the app in debug mode
    app.run(debug=True, host='0.0.0.0', port=5000) 