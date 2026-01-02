from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from .timezone_utils import parse_timestamp, get_current_utc
import logging
from urllib.parse import unquote
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
    logger.info("PyMongo import successful")
except ImportError as e:
    logger.error(f"MongoDB import failed: {e}")
    MONGODB_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_this')

# MongoDB setup and connection management
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
logger.info(f"Using MONGO_URI ending with: ...{MONGO_URI[-20:] if MONGO_URI else 'None'}")
client = None
db = None
timers_collection = None
users_collection = None
pending_users_collection = None

def get_mongodb_client():
    global client, db, timers_collection, users_collection, pending_users_collection
    
    if not MONGODB_AVAILABLE:
        logger.error("MongoDB is not available (pymongo not installed)")
        return None
        
    try:
        if client is None:
            logger.info("Initializing new MongoDB connection...")
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxIdleTimeMS=50000,
                retryWrites=True
            )
            
        # Test the connection
        client.admin.command('ping')
        
        if db is None:
            db = client['axiom']
            timers_collection = db['timers']
            users_collection = db['users']
            pending_users_collection = db['pending_users']
            
        return client
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        logger.error(f"Full error: {traceback.format_exc()}")
        client = None
        return None

# Initialize MongoDB connection
if MONGODB_AVAILABLE:
    try:
        logger.info("Attempting initial MongoDB connection...")
        if get_mongodb_client():
            logger.info("MongoDB connected successfully!")
            # Verify collections
            timer_count = timers_collection.count_documents({})
            logger.info(f"Found {timer_count} documents in timers collection")
    except Exception as e:
        logger.error(f"Initial MongoDB setup failed: {e}")
        logger.error(f"Full error: {traceback.format_exc()}")

# Debug route to check MongoDB connection
@app.route('/debug/mongodb')
def debug_mongodb():
    if 'username' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        status = {
            'MONGODB_AVAILABLE': MONGODB_AVAILABLE,
            'client_connected': client is not None,
            'MONGO_URI_exists': bool(MONGO_URI),
            'MONGO_URI_ends_with': f"...{MONGO_URI[-20:]}" if MONGO_URI else None,
        }
        
        if client:
            # Test the connection
            client.admin.command('ping')
            status['ping_successful'] = True
            
            # Check collections
            db = client['axiom']
            timers = list(db['timers'].find())
            status['timer_count'] = len(timers)
            status['timers'] = [{
                'name': t['name'],
                'kill_time': t.get('kill_time', 'N/A'),
                'spawn_time': t.get('spawn_time', 'N/A'),
                'window_end_time': t.get('window_end_time', 'N/A'),
                'user': t.get('user', 'N/A')
            } for t in timers]
            
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if client is None:
    # Create dummy collections for fallback
    class DummyCollection:
        def find_one(self, *args, **kwargs): return None
        def find(self, *args, **kwargs): return []
        def insert_one(self, *args, **kwargs): 
            class DummyResult:
                def __init__(self): self.inserted_id = None
            return DummyResult()
        def update_one(self, *args, **kwargs): 
            class DummyResult:
                def __init__(self): 
                    self.modified_count = 0
                    self.upserted_id = None
            return DummyResult()
        def delete_one(self, *args, **kwargs): 
            class DummyResult:
                def __init__(self): self.deleted_count = 0
            return DummyResult()
    
    timers_collection = DummyCollection()
    users_collection = DummyCollection()
    pending_users_collection = DummyCollection()

# Hardcoded boss data (edit as needed)

BOSSES = [
    {
        'name': '170',
        'respawn_minutes': 80,
        'window_minutes': 5
    },
    {
        'name': '180',
        'respawn_minutes': 90,
        'window_minutes': 5
    },
    {
        'name': 'Mordy',
        'respawn_minutes': 720,
        'window_minutes': 240
    },
    {
        'name': '210',
        'respawn_minutes': 130,
        'window_minutes': 5
    },
    {
        'name': '215',
        'respawn_minutes': 135,
        'window_minutes': 5
    },
  {
        'name': 'Proteus',
        'respawn_minutes': 720,
        'window_minutes': 240
    },
    {
        'name': 'Dino',
        'respawn_minutes': 1320,
        'window_minutes': 240
    },
    {
        'name': 'Bloodthorn',
        'respawn_minutes': 1320,
        'window_minutes': 240
    },
    {
        'name': 'Gelebron',
        'respawn_minutes': 1320,
        'window_minutes': 240
    },
    {
        'name': 'Crom',
        'respawn_minutes': 5760,
        'window_minutes': 1440
    },
   {
        'name': 'aggy',
        'respawn_minutes': 720,
        'window_minutes': 240
     },
   {
        'name': 'necro',
        'respawn_minutes': 840,
        'window_minutes': 240
    },
{
        'name': 'hrung',
        'respawn_minutes': 840,
        'window_minutes': 240
    }
]

# Admin users (hardcoded)
ADMIN_USERS = {
    'dontcallmeblack': 'dcmb123',
    'neveon': 'sigmaboy',
    'windlord': 'wind123',
    'juliaa':'juliaa123',
    'icymagic':'icy123',
    'SaoThePwincess' : 'pwincess123',
}

# User management functions
def is_admin(username):
    return username in ADMIN_USERS

def get_user_by_username(username):
    return users_collection.find_one({'username': username})

def create_user(username, password):
    user_data = {
        'username': username,
        'password': password,
        'created_at': datetime.utcnow().isoformat(),
        'is_approved': False,
        'is_admin': False
    }
    users_collection.insert_one(user_data)

def approve_user(username):
    try:
        logger.info(f"Attempting to approve user: '{username}'")
        logger.info(f"Username type: {type(username)}, length: {len(username)}")
        logger.info(f"Username bytes: {username.encode('utf-8')}")
        
        # Get the pending user data - try exact match first
        pending_user = pending_users_collection.find_one({'username': username})
        logger.info(f"Pending user found with exact match: {pending_user is not None}")
        
        # If not found, try with stripped whitespace
        if not pending_user:
            stripped_username = username.strip()
            if stripped_username != username:
                logger.info(f"Trying with stripped username: '{stripped_username}'")
                pending_user = pending_users_collection.find_one({'username': stripped_username})
                logger.info(f"Pending user found with stripped username: {pending_user is not None}")
        
        if pending_user:
            logger.info(f"Found pending user: {pending_user}")
            # Create the approved user in the users collection
            user_data = {
                'username': pending_user['username'],
                'password': pending_user['password'],
                'created_at': pending_user['created_at'],
                'is_approved': True,
                'is_admin': False
            }
            logger.info(f"Creating approved user data: {user_data}")
            users_collection.insert_one(user_data)
            logger.info(f"User inserted into users collection")
            
            # Remove from pending collection using the username that was found
            pending_users_collection.delete_one({'username': pending_user['username']})
            logger.info(f"User removed from pending collection")
            return True
        else:
            logger.error(f"No pending user found for username: '{username}'")
            # Let's also check what users are actually in the pending collection
            all_pending = list(pending_users_collection.find())
            logger.info(f"All pending users: {[u.get('username', 'NO_USERNAME') for u in all_pending]}")
            return False
    except Exception as e:
        logger.error(f"Error approving user '{username}': {e}")
        return False

def remove_user(username):
    logger.info(f"Attempting to remove user: '{username}'")
    logger.info(f"Username type: {type(username)}, length: {len(username)}")
    
    # Check if user exists in pending collection
    pending_user = pending_users_collection.find_one({'username': username})
    logger.info(f"Pending user found for removal: {pending_user is not None}")
    
    # If not found in pending, try with stripped whitespace
    if not pending_user:
        stripped_username = username.strip()
        if stripped_username != username:
            logger.info(f"Trying to remove with stripped username: '{stripped_username}'")
            pending_user = pending_users_collection.find_one({'username': stripped_username})
            logger.info(f"Pending user found with stripped username: {pending_user is not None}")
    
    # Check if user exists in approved collection
    approved_user = users_collection.find_one({'username': username})
    logger.info(f"Approved user found for removal: {approved_user is not None}")
    
    # If not found in approved, try with stripped whitespace
    if not approved_user:
        stripped_username = username.strip()
        if stripped_username != username:
            logger.info(f"Trying to remove approved user with stripped username: '{stripped_username}'")
            approved_user = users_collection.find_one({'username': stripped_username})
            logger.info(f"Approved user found with stripped username: {approved_user is not None}")
    
    # Remove from both collections using the username that was found
    if pending_user:
        pending_users_collection.delete_one({'username': pending_user['username']})
        logger.info(f"Removed from pending collection: '{pending_user['username']}'")
    
    if approved_user:
        users_collection.delete_one({'username': approved_user['username']})
        logger.info(f"Removed from approved collection: '{approved_user['username']}'")
    
    # Also try to remove with the original username
    users_collection.delete_one({'username': username})
    pending_users_collection.delete_one({'username': username})
    
    logger.info(f"User '{username}' removal completed")

def get_pending_users():
    try:
        users = list(pending_users_collection.find())
        logger.info(f"Found {len(users)} pending users in database")
        for user in users:
            username = user.get('username', 'NO_USERNAME')
            logger.info(f"Pending user: '{username}' (type: {type(username)}, length: {len(username)})")
        return users
    except Exception as e:
        logger.error(f"Error getting pending users: {e}")
        return []

def get_all_users():
    return list(users_collection.find({'is_approved': True}))

def authenticate_user(username, password):
    # Check admin users first
    if username in ADMIN_USERS and ADMIN_USERS[username] == password:
        return {'username': username, 'is_admin': True, 'is_approved': True}
    
    # Check regular users
    user = get_user_by_username(username)
    if user and user['password'] == password and user['is_approved']:
        return {'username': username, 'is_admin': user.get('is_admin', False), 'is_approved': True}
    
    return None

# MongoDB timer helpers
def load_timers():
    try:
        logger.info("Starting to load timers...")
        timers = {}
        
        # Ensure we have a valid MongoDB connection
        if get_mongodb_client() is None:
            logger.error("Could not establish MongoDB connection, returning empty timers")
            return {}
            
        # Get all timers with retry logic
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            try:
                # Get all timers
                all_docs = list(timers_collection.find())
                logger.info(f"Found {len(all_docs)} timer documents")
                
                for doc in all_docs:
                    try:
                        name = doc.get('name')
                        if name:
                            # Ensure all datetime fields are in correct format
                            for field in ['kill_time', 'spawn_time', 'window_end_time']:
                                if field in doc:
                                    try:
                                        # Verify the timestamp can be parsed
                                        datetime.fromisoformat(doc[field])
                                    except (ValueError, TypeError) as e:
                                        logger.error(f"Invalid timestamp for {name} {field}: {doc[field]}")
                                        # Remove invalid timestamp
                                        doc[field] = None
                            
                            timers[name] = doc
                            logger.info(f"Loaded timer for {name}")
                            logger.info(f"  kill_time={doc.get('kill_time')}")
                            logger.info(f"  spawn_time={doc.get('spawn_time')}")
                            logger.info(f"  window_end_time={doc.get('window_end_time')}")
                        else:
                            logger.warning(f"Found document without name: {doc}")
                    except Exception as e:
                        logger.error(f"Error processing timer document: {e}")
                        continue
                
                # If we got here, break the retry loop
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Error loading timers (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    logger.info("Retrying MongoDB connection...")
                    client = None  # Force new connection on next get_mongodb_client call
                    continue
                else:
                    logger.error("Max retries reached, returning empty timers")
                    return {}
                
        logger.info(f"Successfully loaded {len(timers)} timers")
        return timers
        
    except Exception as e:
        logger.error(f"Error in load_timers: {e}")
        logger.error(traceback.format_exc())
        return {}

def save_timer(boss_name, timer_data):
    try:
        result = timers_collection.update_one({'name': boss_name}, {'$set': timer_data}, upsert=True)
        logger.info(f"MongoDB save result for {boss_name}: {result.modified_count} modified, {result.upserted_id} upserted")
        return True
    except Exception as e:
        logger.error(f"Error saving timer for {boss_name}: {e}")
        return False

def get_boss_by_name(name):
    for boss in BOSSES:
        if boss['name'] == name:
            return boss
    return None

def format_remaining(td):
    try:
        if td is None or not isinstance(td, timedelta):
            logger.warning(f"Invalid timedelta provided: {td}")
            return 'N/A'
            
        total_seconds = int(td.total_seconds())
        if total_seconds <= 0:
            return 'Ready!'
            
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''}, {hours} hr{'s' if hours != 1 else ''}, {minutes} min{'s' if minutes != 1 else ''}"
        elif hours > 0:
            return f"{hours} hr{'s' if hours != 1 else ''}, {minutes} min{'s' if minutes != 1 else ''}"
        else:
            return f"{minutes} min{'s' if minutes != 1 else ''}"
    except Exception as e:
        logger.error(f"Error formatting time: {e}")
        return 'N/A'

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    logger.error(traceback.format_exc())
    return "Internal Server Error", 500

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/debug/users')
def debug_users():
    if 'username' not in session or not session.get('is_admin'):
        return "Access denied", 403
    
    try:
        pending = list(pending_users_collection.find())
        approved = list(users_collection.find())
        
        result = {
            'pending_users': [{'username': u.get('username'), 'created_at': u.get('created_at')} for u in pending],
            'approved_users': [{'username': u.get('username'), 'created_at': u.get('created_at')} for u in approved],
            'total_pending': len(pending),
            'total_approved': len(approved)
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/debug/check-user/<username>')
def debug_check_user(username):
    if 'username' not in session or not session.get('is_admin'):
        return "Access denied", 403
    
    try:
        decoded_username = unquote(username)
        
        # Check in pending collection
        pending_user = pending_users_collection.find_one({'username': decoded_username})
        
        # Check in approved collection
        approved_user = users_collection.find_one({'username': decoded_username})
        
        # Get all pending usernames for comparison
        all_pending = list(pending_users_collection.find())
        all_pending_usernames = [u.get('username', 'NO_USERNAME') for u in all_pending]
        
        result = {
            'search_username': decoded_username,
            'search_username_encoded': username,
            'pending_user_found': pending_user is not None,
            'approved_user_found': approved_user is not None,
            'all_pending_usernames': all_pending_usernames,
            'pending_user_data': pending_user,
            'approved_user_data': approved_user
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/debug/test-username/<username>')
def debug_test_username(username):
    if 'username' not in session or not session.get('is_admin'):
        return "Access denied", 403
    
    try:
        decoded_username = unquote(username)
        
        # Test exact match
        exact_match = pending_users_collection.find_one({'username': decoded_username})
        
        # Test with different variations
        variations = [
            decoded_username,
            decoded_username.strip(),
            decoded_username.lower(),
            decoded_username.upper(),
            decoded_username.replace(' ', ''),
            decoded_username.replace(' ', '_'),
        ]
        
        results = {}
        for var in variations:
            results[var] = pending_users_collection.find_one({'username': var}) is not None
        
        # Get all usernames for comparison
        all_users = list(pending_users_collection.find())
        all_usernames = [u.get('username', 'NO_USERNAME') for u in all_users]
        
        result = {
            'search_username': decoded_username,
            'search_username_encoded': username,
            'exact_match_found': exact_match is not None,
            'variations_tested': results,
            'all_usernames_in_db': all_usernames,
            'exact_match_data': exact_match
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/debug/manual-approve/<username>')
def debug_manual_approve(username):
    if 'username' not in session or not session.get('is_admin'):
        return "Access denied", 403
    
    try:
        decoded_username = unquote(username)
        logger.info(f"Manual approve test for username: '{decoded_username}'")
        
        # Try to approve the user
        success = approve_user(decoded_username)
        
        result = {
            'username': decoded_username,
            'success': success,
            'message': f"User '{decoded_username}' {'approved' if success else 'not approved'}"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/', methods=['GET'])
def index():
    if 'username' not in session:
        flash('You must be logged in to view timers.', 'danger')
        return redirect(url_for('login'))
    timers = load_timers()
    now = get_current_utc()
    due_bosses = []
    upcoming_bosses = []
    lost_bosses = []
    
    logger.info(f"Processing timers at {now.isoformat()}")
    
    for boss in BOSSES:
        timer_entry = timers.get(boss['name'])
        if timer_entry:
            last_kill = timer_entry.get('kill_time')
            last_user = timer_entry.get('user', 'N/A')
            spawn_time = timer_entry.get('spawn_time')
            window_end_time = timer_entry.get('window_end_time')
        else:
            last_kill = None
            last_user = 'N/A'
            spawn_time = None
            window_end_time = None
        
        if last_kill:
            last_kill_dt = parse_timestamp(last_kill)
            if not last_kill_dt:
                logger.error(f"Could not parse last_kill time for {boss['name']}: {last_kill}")
                continue
                
            if spawn_time:
                spawn_dt = parse_timestamp(spawn_time)
                if not spawn_dt:
                    logger.error(f"Could not parse spawn time for {boss['name']}: {spawn_time}")
                    spawn_dt = last_kill_dt + timedelta(minutes=boss['respawn_minutes'])
            else:
                spawn_dt = last_kill_dt + timedelta(minutes=boss['respawn_minutes'])
                
            if window_end_time:
                window_end_dt = parse_timestamp(window_end_time)
                if not window_end_dt:
                    logger.error(f"Could not parse window_end time for {boss['name']}: {window_end_time}")
                    window_end_dt = spawn_dt + timedelta(minutes=boss['window_minutes'])
            else:
                window_end_dt = spawn_dt + timedelta(minutes=boss['window_minutes'])
            
            respawn_remaining = spawn_dt - now
            window_remaining = window_end_dt - now
            respawn_seconds = int(respawn_remaining.total_seconds())
            window_seconds = int(window_remaining.total_seconds())
        else:
            respawn_remaining = window_remaining = None
            respawn_seconds = window_seconds = None
        
        # Determine window display
        if last_kill and respawn_remaining and respawn_remaining.total_seconds() <= 0:
            window_end_display = format_remaining(window_remaining)
            window_seconds_display = window_seconds
        else:
            window_end_display = ''
            window_seconds_display = ''
        
        boss_info = {
            'name': boss['name'],
            'respawn': format_remaining(respawn_remaining) if last_kill else 'N/A',
            'respawn_seconds': respawn_seconds if last_kill else '',
            'window_end': window_end_display if last_kill else 'N/A',
            'window_seconds': window_seconds_display if last_kill else '',
            'last_kill': last_kill_dt.strftime('%Y-%m-%d %H:%M UTC') if last_kill else 'N/A',
            'last_user': last_user,
        }
        
        # Categorize bosses based on their timer status
        if last_kill and respawn_seconds is not None:
            if respawn_seconds <= 0:
                # Boss is in respawn time (spawned)
                if window_seconds is not None and window_seconds <= 0:
                    # Both respawn and window time are done - Lost timer
                    lost_bosses.append(boss_info)
                else:
                    # Boss is spawned but window is still active - Due boss
                    due_bosses.append(boss_info)
            else:
                # Boss is still in respawn time - Upcoming boss
                upcoming_bosses.append(boss_info)
        else:
            # No timer set - Upcoming boss
            upcoming_bosses.append(boss_info)
    
    # Sort upcoming bosses by respawn time (earliest first)
    upcoming_bosses.sort(key=lambda b: b['respawn_seconds'] if isinstance(b['respawn_seconds'], int) and b['respawn_seconds'] > 0 else float('inf'))
    
    # Sort due bosses by window time (earliest first)
    due_bosses.sort(key=lambda b: b['window_seconds'] if isinstance(b['window_seconds'], int) and b['window_seconds'] > 0 else float('inf'))
    
    # Sort lost bosses by last kill time (most recent first)
    lost_bosses.sort(key=lambda b: b['last_kill'], reverse=True)
    
    username = session.get('username')
    return render_template_string(TEMPLATE, 
                                due_bosses=due_bosses, 
                                upcoming_bosses=upcoming_bosses, 
                                lost_bosses=lost_bosses,
                                username=username, 
                                now=datetime.utcnow)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Decode URL-encoded username and password
        if username:
            username = unquote(username)
        if password:
            password = unquote(password)
            
        user = authenticate_user(username, password)
        if user:
            session['username'] = username
            session['is_admin'] = user['is_admin']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template_string(LOGIN_TEMPLATE, now=datetime.utcnow)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        logger.info(f"Registration - Raw username from form: '{username}'")
        logger.info(f"Registration - Raw password from form: '{password}'")
        
        # Decode URL-encoded username and password
        if username:
            username = unquote(username)
        if password:
            password = unquote(password)
        
        logger.info(f"Registration - Decoded username: '{username}'")
        logger.info(f"Registration - Username type: {type(username)}, length: {len(username)}")
        
        # Trim whitespace from username
        username = username.strip()
        logger.info(f"Registration - Trimmed username: '{username}'")
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template_string(REGISTER_TEMPLATE)
        
        # Check if username already exists
        if get_user_by_username(username) or username in ADMIN_USERS:
            flash('Username already exists.', 'danger')
            return render_template_string(REGISTER_TEMPLATE)
        
        # Create pending user
        pending_user_data = {
            'username': username,
            'password': password,
            'created_at': datetime.utcnow().isoformat()
        }
        logger.info(f"Registration - Creating pending user data: {pending_user_data}")
        pending_users_collection.insert_one(pending_user_data)
        logger.info(f"Registration - User '{username}' inserted into pending collection")
        
        flash('Registration submitted! Please wait for admin approval.', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/admin')
def admin_panel():
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    pending_users = get_pending_users()
    approved_users = get_all_users()
    
    # Debug: Log pending users
    logger.info(f"Admin panel - Pending users found: {[user['username'] for user in pending_users]}")
    logger.info(f"Admin panel - Approved users found: {[user['username'] for user in approved_users]}")
    
    return render_template_string(ADMIN_TEMPLATE, 
                                pending_users=pending_users, 
                                approved_users=approved_users,
                                username=session['username'])

@app.route('/admin/approve/<username>')
def approve_user_route(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Decode URL-encoded username
    decoded_username = unquote(username)
    logger.info(f"Admin approve route - Original username: '{username}'")
    logger.info(f"Admin approve route - Decoded username: '{decoded_username}'")
    
    success = approve_user(decoded_username)
    
    if success:
        flash(f'User {decoded_username} approved successfully.', 'success')
    else:
        flash(f'Failed to approve user {decoded_username}. User may not exist in pending list.', 'danger')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/remove/<username>')
def remove_user_route(username):
    if 'username' not in session or not session.get('is_admin'):
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Decode URL-encoded username
    decoded_username = unquote(username)
    logger.info(f"Admin remove route - Original username: '{username}'")
    logger.info(f"Admin remove route - Decoded username: '{decoded_username}'")
    
    if decoded_username == session['username']:
        flash('You cannot remove yourself.', 'danger')
        return redirect(url_for('admin_panel'))
    
    remove_user(decoded_username)
    flash(f'User {decoded_username} removed successfully.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/reset/<boss_name>', methods=['GET', 'POST'])
def reset(boss_name):
    if 'username' not in session:
        flash('You must be logged in to reset timers.', 'danger')
        return redirect(url_for('login'))
    boss = get_boss_by_name(boss_name)
    if not boss:
        flash('Boss not found.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            kill_dt = datetime.utcnow()
            spawn_dt = kill_dt + timedelta(minutes=boss['respawn_minutes'])
            window_end_dt = spawn_dt + timedelta(minutes=boss['window_minutes'])
            timer_data = {
                "name": boss_name,
                "kill_time": kill_dt.isoformat(),
                "spawn_time": spawn_dt.isoformat(),
                "window_end_time": window_end_dt.isoformat(),
                "user": session['username']
            }
            logger.info(f"Resetting timer for {boss_name}: {timer_data}")
            save_timer(boss_name, timer_data)
            logger.info(f"Timer saved successfully for {boss_name}")
            flash(f'{boss_name} timer reset!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error resetting timer for {boss_name}: {e}")
            flash(f'Error resetting timer: {str(e)}', 'danger')
            return redirect(url_for('index'))
    return render_template_string(RESET_TEMPLATE, boss=boss, now_func=datetime.utcnow)

@app.route('/edit/<boss_name>', methods=['GET', 'POST'])
def edit(boss_name):
    if 'username' not in session:
        flash('You must be logged in to edit timers.', 'danger')
        return redirect(url_for('login'))
    boss = get_boss_by_name(boss_name)
    if not boss:
        flash('Boss not found.', 'danger')
        return redirect(url_for('index'))
    timers = load_timers()
    timer_entry = timers.get(boss_name)
    if not timer_entry:
        flash('No timer to edit for this boss.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            minutes = int(request.form.get('minutes', 0))
            if minutes <= 0:
                flash('Please enter a positive number of minutes.', 'danger')
                return redirect(url_for('edit', boss_name=boss_name))
        except Exception:
            flash('Invalid input.', 'danger')
            return redirect(url_for('edit', boss_name=boss_name))
        # Reduce kill_time, spawn_time, window_end_time by minutes
        for key in ['kill_time', 'spawn_time', 'window_end_time']:
            if timer_entry.get(key):
                dt = datetime.fromisoformat(timer_entry[key])
                dt -= timedelta(minutes=minutes)
                timer_entry[key] = dt.isoformat()
        save_timer(boss_name, timer_entry)
        flash(f'{boss_name} timer reduced by {minutes} minutes!', 'success')
        return redirect(url_for('index'))
    return render_template_string(EDIT_TEMPLATE, boss=boss, boss_name=boss_name)

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axiom Timers</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Montserrat', Arial, sans-serif;
            background: #181a20;
            color: #e0e6ed;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .container {
            max-width: 95vw;
            width: 100%;
            margin: 4vh auto 2vh auto;
            background: #23262f;
            padding: 4vw 2vw 3vw 2vw;
            border-radius: 1.2rem;
            box-shadow: 0 0.4rem 2.4rem #000a, 0 0.15rem 0.4rem #0004;
        }
        h1 {
            text-align: center;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin-bottom: 1em;
            font-size: 2.2rem;
        }
        .topbar {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-bottom: 2vh;
            gap: 1vw;
        }
        .username {
            margin-right: 1vw;
            font-weight: 600;
            color: #7dd3fc;
            font-size: 1.1rem;
        }
        .boss-section {
            margin-bottom: 2.5em;
        }
        .boss-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
            gap: 1.2em;
            margin-top: 1.2em;
        }
        .boss-card {
            background: #232b3a;
            border-radius: 1em;
            box-shadow: 0 0.2em 1em #0003;
            padding: 1.2em 1em 1em 1em;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            position: relative;
            min-width: 0;
        }
        .boss-header {
            display: flex;
            align-items: center;
            width: 100%;
            margin-bottom: 0.7em;
        }
        .boss-name {
            font-size: 1.25rem;
            font-weight: 700;
            flex: 1;
            color: #7dd3fc;
            word-break: break-word;
        }
        .boss-status {
            font-size: 0.95em;
            font-weight: 600;
            padding: 0.25em 0.8em;
            border-radius: 1em;
            background: #22c55e33;
            color: #22c55e;
            margin-left: 0.5em;
        }
        .boss-status.upcoming {
            background: #2563eb33;
            color: #3b82f6;
        }
        .boss-status.lost {
            background: #ef444433;
            color: #ef4444;
        }
        .boss-info {
            margin-bottom: 0.5em;
            width: 100%;
        }
        .boss-label {
            font-weight: 600;
            color: #94a3b8;
            font-size: 0.98em;
            margin-right: 0.3em;
        }
        .boss-value {
            font-size: 1em;
            color: #e0e6ed;
        }
        .boss-action {
            width: 100%;
            margin-top: 0.7em;
            display: flex;
            justify-content: flex-end;
            gap: 3em;
        }
        .boss-action a.button, .boss-action button {
            background: linear-gradient(90deg, #ff512f 0%, #dd2476 100%);
            color: #fff;
            padding: 0.7em 1.3em;
            border-radius: 0.5em;
            text-decoration: none;
            font-weight: 700;
            border: none;
            cursor: pointer;
            box-shadow: 0 0.2em 0.8em #dd247655, 0 0.1em 0.3em #0002;
            transition: background 0.18s, box-shadow 0.18s, transform 0.12s;
            outline: none;
            display: inline-block;
            margin: 0.3em 0;
            font-size: 1.1rem;
            letter-spacing: 0.03em;
            position: relative;
            overflow: hidden;
        }
        .boss-action a.button:hover, .boss-action button:hover, .boss-action a.button:focus, .boss-action button:focus {
            background: linear-gradient(90deg, #ff512f 0%, #f09819 100%);
            box-shadow: 0 0.4em 1.6em #ff512f55, 0 0.1em 0.3em #0003;
            transform: translateY(-2px) scale(1.03);
        }
        .boss-action a.button:active, .boss-action button:active {
            background: linear-gradient(90deg, #dd2476 0%, #ff512f 100%);
            box-shadow: 0 0.1em 0.3em #ff512f33;
            transform: scale(0.98);
        }
        .flash {
            padding: 1em;
            margin-bottom: 1.2em;
            border-radius: 0.5em;
            font-weight: 600;
            letter-spacing: 0.03em;
            font-size: 1rem;
        }
        .flash-success {
            background: #22c55e33;
            color: #22c55e;
        }
        .flash-danger {
            background: #ef444433;
            color: #ef4444;
        }
        /* Responsive styles */
        @media (max-width: 600px) {
            .container {
                padding: 2vw 1vw 2vw 1vw;
            }
            h1 {
                font-size: 1.4rem;
            }
            .topbar {
                flex-direction: column;
                align-items: stretch;
                gap: 1vw;
                margin-bottom: 1em;
            }
            .username {
                margin-right: 0;
                margin-bottom: 0.2em;
                text-align: left;
                font-size: 1rem;
            }
            .boss-cards {
                grid-template-columns: 1fr;
                gap: 1em;
            }
            .boss-card {
                padding: 1em 0.7em 0.8em 0.7em;
            }
            .boss-name {
                font-size: 1.1rem;
            }
            th, td {
                padding: 0.7em 0.2em;
                font-size: 0.98rem;
            }
            table, thead, tbody, th, td, tr {
                display: block;
            }
            table {
                width: 100%;
                overflow-x: hidden;
                background: none;
            }
            thead {
                display: none;
            }
            tr {
                margin-bottom: 1em;
                box-shadow: 0 0.1em 0.4em #0002;
                border-radius: 0.7em;
                background: #23262f;
                display: block;
                padding: 0.4em 0.1em;
            }
            td {
                border: none;
                position: relative;
                padding-left: 44%;
                text-align: left;
                min-height: 2em;
                display: flex;
                align-items: center;
                font-size: 0.98rem;
                margin-bottom: 0.15em;
                background: none;
            }
            td:before {
                position: absolute;
                left: 0.6em;
                width: 40%;
                white-space: nowrap;
                font-weight: 700;
                color: #7dd3fc;
                content: attr(data-label);
                font-size: 0.98rem;
            }
            td:last-child {
                justify-content: flex-start;
            }
            a.button, button {
                width: 100%;
                margin: 0.2em 0;
                font-size: 1rem;
                padding: 0.7em 0.4em;
            }
        }
        @media (max-width: 400px) {
            h1 {
                font-size: 1.1rem;
            }
            .container {
                padding: 1vw 0.5vw 1vw 0.5vw;
            }
        }
        footer {
            text-align: center;
            color: #64748b;
            font-size: 0.95rem;
            margin-top: 2em;
            margin-bottom: 1em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Axiom Timers</h1>
        <div class="topbar">
            {% if username %}
                <span class="username">Logged in as {{ username }}</span>
                {% if session.get('is_admin') %}
                    <a class="button" href="/admin" style="background:linear-gradient(90deg,#f59e0b 0%,#d97706 100%);margin-right:0.5em;">Admin Panel</a>
                {% endif %}
                <a class="button" href="/logout">Logout</a>
            {% else %}
                <a class="button" href="/login">Login</a>
                <a class="button" href="/register" style="background:linear-gradient(90deg,#10b981 0%,#059669 100%);margin-left:0.5em;">Register</a>
            {% endif %}
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% if due_bosses %}
        <div class="boss-section">
        <h2 style="color:#22c55e; text-align:center; margin-top:1em;">Due Bosses</h2>
            <div class="boss-cards">
            {% for boss in due_bosses %}
                <div class="boss-card">
                    <div class="boss-header">
                        <span class="boss-name">{{ boss.name }}</span>
                        <span class="boss-status">Due</span>
                    </div>
                    <div class="boss-info"><span class="boss-label">Last Reset By:</span> <span class="boss-value">{{ boss.last_user }}</span></div>
                    <div class="boss-info"><span class="boss-label">Window End:</span> <span class="boss-value"><span class="window-timer" id="window-{{ boss.name }}" data-initial-seconds="{{ boss.window_seconds }}">{{ boss.window_end }}</span></span></div>
                    <div class="boss-action">
                    {% if username %}
                        <a class="button" href="/reset/{{ boss.name }}">Reset</a>
                        <a class="button" href="/edit/{{ boss.name }}" style="margin-left:0.5em;background:linear-gradient(90deg,#2563eb 0%,#3b82f6 100%)">Edit</a>
                    {% else %}
                        <a class="button" href="/login">Login to Reset</a>
                    {% endif %}
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}
        <div class="boss-section">
        <h2 style="color:#7dd3fc; text-align:center; margin-top:2em;">Upcoming Bosses</h2>
            <div class="boss-cards">
            {% for boss in upcoming_bosses %}
                <div class="boss-card">
                    <div class="boss-header">
                        <span class="boss-name">{{ boss.name }}</span>
                        <span class="boss-status upcoming">Upcoming</span>
                    </div>
                    <div class="boss-info"><span class="boss-label">Last Reset By:</span> <span class="boss-value">{{ boss.last_user }}</span></div>
                    <div class="boss-info"><span class="boss-label">Next Spawn:</span> <span class="boss-value"><span class="respawn-timer" id="respawn-{{ boss.name }}" data-initial-seconds="{{ boss.respawn_seconds }}">{{ boss.respawn }}</span></span></div>
                    <div class="boss-action">
                    {% if username %}
                        <a class="button" href="/reset/{{ boss.name }}">Reset</a>
                        <a class="button" href="/edit/{{ boss.name }}">Edit</a>
                    {% else %}
                        <a class="button" href="/login">Login to Reset</a>
                    {% endif %}
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% if lost_bosses %}
        <div class="boss-section">
        <h2 style="color:#ef4444; text-align:center; margin-top:2em;">Lost Bosses</h2>
            <div class="boss-cards">
            {% for boss in lost_bosses %}
                <div class="boss-card">
                    <div class="boss-header">
                        <span class="boss-name">{{ boss.name }}</span>
                        <span class="boss-status lost">Lost</span>
                    </div>
                    <div class="boss-info"><span class="boss-label">Last Kill:</span> <span class="boss-value">{{ boss.last_kill }}</span></div>
                    <div class="boss-info"><span class="boss-label">Last Reset By:</span> <span class="boss-value">{{ boss.last_user }}</span></div>
                    <div class="boss-action">
                    {% if username %}
                        <a class="button" href="/reset/{{ boss.name }}">Reset</a>
                    {% else %}
                        <a class="button" href="/login">Login to Reset</a>
                    {% endif %}
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
    <footer>
        &copy; {{ now().year }} Axiom Clan Timers &mdash; Powered by Flask
    </footer>
    <script>
    function formatCountdown(seconds) {
        if (seconds === null || seconds === '' || isNaN(seconds)) return '';
        if (seconds <= 0) return 'Ready!';
        
        let days = Math.floor(seconds / 86400);
        let hours = Math.floor((seconds % 86400) / 3600);
        let minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) {
            return `${days} day${days !== 1 ? 's' : ''}, ${hours} hr${hours !== 1 ? 's' : ''}, ${minutes} min${minutes !== 1 ? 's' : ''}`;
        } else if (hours > 0) {
            return `${hours} hr${hours !== 1 ? 's' : ''}, ${minutes} min${minutes !== 1 ? 's' : ''}`;
        } else {
            return `${minutes} min${minutes !== 1 ? 's' : ''}`;
        }
    }
    
    // Store initial timestamps for accurate timing
    let initialTimestamps = {};
    
    function updateTimers() {
        const now = Date.now();
        
        document.querySelectorAll('.respawn-timer').forEach(function(el) {
            let initialSeconds = parseInt(el.getAttribute('data-initial-seconds'));
            let initialTime = initialTimestamps[el.id] || now;
            
            if (!initialTimestamps[el.id]) {
                initialTimestamps[el.id] = now;
            }
            
            if (isNaN(initialSeconds) || el.innerText === 'N/A') return;
            
            // Calculate elapsed time and remaining seconds
            const elapsedSeconds = Math.floor((now - initialTime) / 1000);
            const remainingSeconds = initialSeconds - elapsedSeconds;
            
            // Update text timer
            if (remainingSeconds > 0) {
                el.innerText = formatCountdown(remainingSeconds);
                // Hide window timer if respawn is not ready
                let windowEl = el.parentElement.parentElement.querySelector('.window-timer');
                if (windowEl) {
                    windowEl.innerText = '';
                }
            } else {
                el.innerText = 'Ready!';
                // Show window timer if available
                let windowEl = el.parentElement.parentElement.querySelector('.window-timer');
                if (windowEl) {
                    let wInitialSeconds = parseInt(windowEl.getAttribute('data-initial-seconds'));
                    let wInitialTime = initialTimestamps[windowEl.id] || now;
                    
                    if (!initialTimestamps[windowEl.id]) {
                        initialTimestamps[windowEl.id] = now;
                    }
                    
                    if (!isNaN(wInitialSeconds) && wInitialSeconds > 0) {
                        const wElapsedSeconds = Math.floor((now - wInitialTime) / 1000);
                        const wRemainingSeconds = wInitialSeconds - wElapsedSeconds;
                        
                        if (wRemainingSeconds > 0) {
                            windowEl.innerText = formatCountdown(wRemainingSeconds);
                        } else {
                            windowEl.innerText = '';
                        }
                    } else {
                        windowEl.innerText = '';
                    }
                }
            }
        });
        
        // Also update window timers that are already running
        document.querySelectorAll('.window-timer').forEach(function(el) {
            let respawnEl = el.parentElement.parentElement.querySelector('.respawn-timer');
            if (respawnEl && respawnEl.innerText !== 'Ready!') return; // Only update if respawn is ready
            
            let initialSeconds = parseInt(el.getAttribute('data-initial-seconds'));
            let initialTime = initialTimestamps[el.id] || now;
            
            if (!initialTimestamps[el.id]) {
                initialTimestamps[el.id] = now;
            }
            
            if (isNaN(initialSeconds) || el.innerText === 'N/A') return;
            
            const elapsedSeconds = Math.floor((now - initialTime) / 1000);
            const remainingSeconds = initialSeconds - elapsedSeconds;
            
            if (remainingSeconds > 0) {
                el.innerText = formatCountdown(remainingSeconds);
            } else {
                el.innerText = '';
            }
        });
    }
    
    // Use setInterval for efficient 60-second updates
    setInterval(updateTimers, 60000);
    
    // Also update on page visibility change to catch up when tab becomes active
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // Just update timers when tab becomes visible, don't reset timestamps
            updateTimers();
        }
    });
    
    window.onload = updateTimers;
    </script>
    {% if username == 'dontcallmeblack' %}
    <script>
    (function() {
        // Request notification permission if not already granted
        if (Notification.permission !== "granted") {
            Notification.requestPermission();
        }

        // Keep track of which bosses we've already notified for in this session
        var notifiedBosses = {};
        var targetBosses = ['170', '180', '210', '215'];

        function checkBossNotifications() {
            if (Notification.permission !== "granted") return;

            targetBosses.forEach(function(bossName) {
                var el = document.getElementById('respawn-' + bossName);
                if (el) {
                    var text = el.innerText;
                    
                    // If the text says "Ready!" and we haven't notified yet
                    if (text === 'Ready!' && !notifiedBosses[bossName]) {
                        new Notification("Boss Ready!", { 
                            body: bossName + " has spawned and is ready to kill!",
                            icon: "https://via.placeholder.com/128/ff0000/ffffff?text=BOSS"
                        });
                        notifiedBosses[bossName] = true;
                    }
                    
                    // If the text is NOT "Ready!" (meaning timer was reset), reset the notification flag
                    if (text !== 'Ready!' && notifiedBosses[bossName]) {
                        notifiedBosses[bossName] = false;
                    }
                }
            });
        }

        // Check every 5 seconds
        setInterval(checkBossNotifications, 5000);
    })();
    </script>
    {% endif %}
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Axiom Timers</title>
    <style>
        body { font-family: Arial, sans-serif; background: #181a20; color: #eee; margin: 0; padding: 0; }
        .container { max-width: 400px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 10px; box-shadow: 0 2px 8px #0008; }
        h2 { text-align: center; }
        form { display: flex; flex-direction: column; gap: 1em; }
        label { font-weight: bold; }
        input { padding: 0.5em; border-radius: 5px; border: none; }
        button { background: #3b82f6; color: #fff; padding: 0.7em; border: none; border-radius: 5px; font-size: 1em; cursor: pointer; }
        button:hover { background: #2563eb; }
        a { color: #3b82f6; text-decoration: none; }
        .flash { padding: 1em; margin-bottom: 1em; border-radius: 5px; }
        .flash-success { background: #22c55e; color: #fff; }
        .flash-danger { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Login</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="post">
            <label for="username">Username:</label>
            <input type="text" name="username" id="username" required>
            <label for="password">Password:</label>
            <input type="password" name="password" id="password" required>
            <button type="submit">Login</button>
        </form>
        <p style="text-align: center; margin-top: 1.5em;">
            <a href="/register" style="color: #10b981; text-decoration: none; font-weight: 600;">Don't have an account? Register here</a>
        </p>
        <p><a href="/">Back to Timers</a></p>
    </div>
</body>
</html>
'''

RESET_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset {{ boss.name }} Timer</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Montserrat', Arial, sans-serif; background: #181a20; color: #e0e6ed; margin: 0; padding: 0; }
        .container { max-width: 400px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 18px; box-shadow: 0 2px 8px #0008; }
        h2 { text-align: center; }
        form { display: flex; flex-direction: column; gap: 1.5em; }
        button { background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%); color: #fff; padding: 0.7em; border: none; border-radius: 7px; font-size: 1em; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px #2563eb33; transition: background 0.2s, box-shadow 0.2s; outline: none; }
        button:hover { background: linear-gradient(90deg, #1e40af 0%, #2563eb 100%); box-shadow: 0 4px 16px #2563eb55; }
        a { color: #3b82f6; text-decoration: none; text-align: center; margin-top: 1em; display: block; }
        .flash { padding: 1em; margin-bottom: 1em; border-radius: 7px; font-weight: 600; letter-spacing: 0.5px; }
        .flash-success { background: #22c55e33; color: #22c55e; }
        .flash-danger { background: #ef444433; color: #ef4444; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Reset {{ boss.name }} Timer</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="post">
            <div style="text-align:center; font-size:1.1em; margin-bottom:1em;">Are you sure you want to reset the timer for <b>{{ boss.name }}</b>?</div>
            <button type="submit">Confirm Reset</button>
        </form>
        <a href="/">Back to Timers</a>
    </div>
</body>
</html>
'''

EDIT_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit {{ boss.name }} Timer</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Montserrat', Arial, sans-serif; background: #181a20; color: #e0e6ed; margin: 0; padding: 0; }
        .container { max-width: 400px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 18px; box-shadow: 0 2px 8px #0008; }
        h2 { text-align: center; }
        form { display: flex; flex-direction: column; gap: 1.5em; }
        label { font-weight: bold; }
        input { padding: 0.5em; border-radius: 5px; border: none; }
        button { background: linear-gradient(90deg, #ff512f 0%, #dd2476 100%); color: #fff; padding: 0.7em; border: none; border-radius: 7px; font-size: 1em; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px #dd247655; transition: background 0.2s, box-shadow 0.2s; outline: none; }
        button:hover { background: linear-gradient(90deg, #ff512f 0%, #f09819 100%); box-shadow: 0 4px 16px #ff512f55; }
        a { color: #3b82f6; text-decoration: none; text-align: center; margin-top: 1em; display: block; }
        .flash { padding: 1em; margin-bottom: 1em; border-radius: 7px; font-weight: 600; letter-spacing: 0.5px; }
        .flash-success { background: #22c55e33; color: #22c55e; }
        .flash-danger { background: #ef444433; color: #ef4444; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Edit {{ boss.name }} Timer</h2>
        <form method="post">
            <label for="minutes">How many minutes to reduce from timer?</label>
            <input type="number" name="minutes" id="minutes" min="1" required>
            <button type="submit">Reduce Timer</button>
        </form>
        <a href="/">Back to Timers</a>
    </div>
</body>
</html>
'''

REGISTER_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - Axiom MMO Timers</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Montserrat', Arial, sans-serif; background: #181a20; color: #e0e6ed; margin: 0; padding: 0; }
        .container { max-width: 400px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 18px; box-shadow: 0 2px 8px #0008; }
        h2 { text-align: center; margin-bottom: 1.5em; }
        .info-box { background: #1e293b; padding: 1em; border-radius: 10px; margin-bottom: 1.5em; border-left: 4px solid #3b82f6; }
        .info-box p { margin: 0; font-size: 0.9em; color: #94a3b8; }
        form { display: flex; flex-direction: column; gap: 1.5em; }
        label { font-weight: bold; color: #e0e6ed; }
        input { padding: 0.8em; border-radius: 8px; border: 1px solid #374151; background: #1f2937; color: #e0e6ed; font-size: 1em; }
        input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px #3b82f633; }
        button { background: linear-gradient(90deg, #10b981 0%, #059669 100%); color: #fff; padding: 0.8em; border: none; border-radius: 8px; font-size: 1em; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px #10b98133; transition: background 0.2s, box-shadow 0.2s; outline: none; }
        button:hover { background: linear-gradient(90deg, #059669 0%, #047857 100%); box-shadow: 0 4px 16px #10b98155; }
        a { color: #3b82f6; text-decoration: none; text-align: center; margin-top: 1em; display: block; }
        .flash { padding: 1em; margin-bottom: 1em; border-radius: 8px; font-weight: 600; letter-spacing: 0.5px; }
        .flash-success { background: #22c55e33; color: #22c55e; }
        .flash-danger { background: #ef444433; color: #ef4444; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Register for Axiom Timers</h2>
        <div class="info-box">
            <p><strong>Important:</strong> Use your main character name as the username. This will be visible to other clan members when you reset timers.</p>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="post">
            <label for="username">Character Name (Main Toon):</label>
            <input type="text" name="username" id="username" required placeholder="Enter your main character name">
            <label for="password">Password:</label>
            <input type="password" name="password" id="password" required placeholder="Choose a password">
            <button type="submit">Register</button>
        </form>
        <a href="/login">Already have an account? Login</a>
    </div>
</body>
</html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - Axiom Timers</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Montserrat', Arial, sans-serif; background: #181a20; color: #e0e6ed; margin: 0; padding: 0; }
        .container { max-width: 95vw; width: 100%; margin: 4vh auto 2vh auto; background: #23262f; padding: 4vw 2vw 3vw 2vw; border-radius: 1.2rem; box-shadow: 0 0.4rem 2.4rem #000a, 0 0.15rem 0.4rem #0004; }
        h1, h2 { text-align: center; font-weight: 700; letter-spacing: 0.12em; margin-bottom: 1em; }
        h1 { font-size: 2.2rem; }
        h2 { font-size: 1.5rem; color: #7dd3fc; }
        .topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2vh; }
        .username { font-weight: 600; color: #7dd3fc; font-size: 1.1rem; }
        .section { margin-bottom: 3em; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.2em; margin-top: 1.2em; }
        .user-card { background: #232b3a; border-radius: 1em; box-shadow: 0 0.2em 1em #0003; padding: 1.2em; }
        .user-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.7em; }
        .user-name { font-size: 1.1rem; font-weight: 700; color: #7dd3fc; }
        .user-date { font-size: 0.9em; color: #94a3b8; }
        .user-actions { display: flex; gap: 0.5em; }
        .button { padding: 0.5em 1em; border-radius: 0.5em; text-decoration: none; font-weight: 600; border: none; cursor: pointer; font-size: 0.9rem; }
        .button.approve { background: linear-gradient(90deg, #10b981 0%, #059669 100%); color: #fff; }
        .button.remove { background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%); color: #fff; }
        .button.back { background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%); color: #fff; }
        .flash { padding: 1em; margin-bottom: 1.2em; border-radius: 0.5em; font-weight: 600; letter-spacing: 0.03em; font-size: 1rem; }
        .flash-success { background: #22c55e33; color: #22c55e; }
        .flash-danger { background: #ef444433; color: #ef4444; }
        .empty-state { text-align: center; color: #94a3b8; font-style: italic; padding: 2em; }
        @media (max-width: 600px) {
            .container { padding: 2vw 1vw; }
            h1 { font-size: 1.4rem; }
            .topbar { flex-direction: column; gap: 1vw; }
            .user-grid { grid-template-columns: 1fr; }
            .user-actions { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Admin Panel</h1>
        <div class="topbar">
            <span class="username">Logged in as {{ username }}</span>
            <a class="button back" href="/">Back to Timers</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        
        <div class="section">
            <h2>Pending Approvals</h2>
            {% if pending_users %}
                <div class="user-grid">
                    {% for user in pending_users %}
                    <div class="user-card">
                        <div class="user-header">
                            <span class="user-name">{{ user.username }}</span>
                            <span class="user-date">{{ user.created_at[:10] }}</span>
                        </div>
                        <div class="user-actions">
                            <a href="/admin/approve/{{ user.username }}" class="button approve">Approve</a>
                            <a href="/admin/remove/{{ user.username }}" class="button remove">Remove</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="empty-state">No pending users to approve.</div>
            {% endif %}
        </div>
        
        <div class="section">
            <h2>Approved Users</h2>
            {% if approved_users %}
                <div class="user-grid">
                    {% for user in approved_users %}
                    <div class="user-card">
                        <div class="user-header">
                            <span class="user-name">{{ user.username }}</span>
                            <span class="user-date">{{ user.created_at[:10] }}</span>
                        </div>
                        <div class="user-actions">
                            <a href="/admin/remove/{{ user.username }}" class="button remove">Remove</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="empty-state">No approved users.</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''
