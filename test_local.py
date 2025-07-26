#!/usr/bin/env python3
"""
Local test script for Axiom Timer App
Run this to test the app locally without deploying
"""

import os
from api.index import app

if __name__ == '__main__':
    # Set environment variables for local testing
    os.environ['SECRET_KEY'] = 'test_secret_key_change_this'
    os.environ['MONGO_URI'] = 'mongodb+srv://dcmbch7:EDxClAIUCaBpcD7z@cluster0.z0dys6f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
    
    print("🚀 Starting Axiom Timer App locally...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("🔑 Admin users: dontcallmeblack, neveon, windlord, snail, icymagic")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Run the app in debug mode
    app.run(debug=True, host='0.0.0.0', port=5000) 