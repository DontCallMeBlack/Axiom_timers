from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'axiom_secret_key'  # Change this for production

# Hardcoded boss data (edit as needed)
BOSSES = [
    {
        'name': '170',
        'respawn_minutes': 70,
        'window_minutes': 5
    },
    {
        'name': '180',
        'respawn_minutes': 80,
        'window_minutes': 5
    },
    {
        'name': '210',
        'respawn_minutes': 130,
        'window_minutes': 5
    },
    {
        'name': '215',
        'respawn_minutes': 140,
        'window_minutes': 5
    },
        {
        'name': 'Proteus',
        'respawn_minutes': 960,
        'window_minutes': 15
    },
    {
        'name': 'Dino',
        'respawn_minutes': 1680,
        'window_minutes': 960
    },
    {
        'name': 'Bloodthorn',
        'respawn_minutes': 1680,
        'window_minutes': 960
    },
    {
        'name': 'Gelebron',
        'respawn_minutes': 1680,
        'window_minutes': 960
    }

] 

# Hardcoded users (edit as needed)
USERS = {
    'dontcallmeblack': 'dcmb',
    'neveon': 'sigmaboy',
    'azazelbreath': 'lezaza',
}

TIMERS_FILE = os.path.join(os.path.dirname(__file__), '../bosses.json')

def load_timers():
    if not os.path.exists(TIMERS_FILE):
        timers = {boss['name']: None for boss in BOSSES}
        with open(TIMERS_FILE, 'w') as f:
            json.dump(timers, f)
        return timers
    with open(TIMERS_FILE, 'r') as f:
        return json.load(f)

def save_timers(timers):
    with open(TIMERS_FILE, 'w') as f:
        json.dump(timers, f)

def get_boss_by_name(name):
    for boss in BOSSES:
        if boss['name'] == name:
            return boss
    return None

def format_remaining(td):
    if td is None or td.total_seconds() <= 0:
        return 'Ready!'
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'

@app.route('/', methods=['GET'])
def index():
    timers = load_timers()
    now = datetime.utcnow()
    due_bosses = []
    not_due_bosses = []
    for boss in BOSSES:
        timer_entry = timers.get(boss['name'])
        if timer_entry and isinstance(timer_entry, dict):
            last_kill = timer_entry.get('kill_time')
            last_user = timer_entry.get('user', 'N/A')
        else:
            last_kill = timer_entry
            last_user = 'N/A'
        if last_kill:
            last_kill_dt = datetime.fromisoformat(last_kill)
            respawn = last_kill_dt + timedelta(minutes=boss['respawn_minutes'])
            window_end = respawn + timedelta(minutes=boss['window_minutes'])
            respawn_remaining = respawn - now
            window_remaining = window_end - now
            respawn_seconds = int(respawn_remaining.total_seconds())
            window_seconds = int(window_remaining.total_seconds())
        else:
            respawn_remaining = window_remaining = None
            respawn_seconds = window_seconds = None
        if last_kill and respawn_remaining.total_seconds() <= 0:
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
        if last_kill and respawn_seconds is not None and respawn_seconds <= 0:
            due_bosses.append(boss_info)
        else:
            not_due_bosses.append(boss_info)
    not_due_bosses.sort(key=lambda b: b['respawn_seconds'] if isinstance(b['respawn_seconds'], int) and b['respawn_seconds'] > 0 else float('inf'))
    username = session.get('username')
    return render_template_string(TEMPLATE, bosses=not_due_bosses, due_bosses=due_bosses, username=username, now=datetime.utcnow)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if USERS.get(username) == password:
            session['username'] = username
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template_string(LOGIN_TEMPLATE, now=datetime.utcnow)

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
        kill_dt = datetime.utcnow()
        timers = load_timers()
        timers[boss_name] = {"kill_time": kill_dt.isoformat(), "user": session['username']}
        save_timers(timers)
        flash(f'{boss_name} timer reset!', 'success')
        return redirect(url_for('index'))
    return render_template_string(RESET_TEMPLATE, boss=boss, now_func=datetime.utcnow)

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
            max-width: 700px;
            margin: 40px auto 20px auto;
            background: #23262f;
            padding: 2.5em 2em 2em 2em;
            border-radius: 18px;
            box-shadow: 0 4px 24px #000a, 0 1.5px 4px #0004;
        }
        h1 {
            text-align: center;
            font-weight: 700;
            letter-spacing: 2px;
            margin-bottom: 0.5em;
        }
        .topbar {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-bottom: 1.5em;
        }
        .username {
            margin-right: 1em;
            font-weight: 600;
            color: #7dd3fc;
        }
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 0.5em;
            margin-top: 1em;
        }
        th, td {
            padding: 1em 0.5em;
            text-align: center;
        }
        th {
            background: #232b3a;
            color: #7dd3fc;
            font-weight: 700;
            border-radius: 8px 8px 0 0;
            border-bottom: 2px solid #334155;
        }
        tr {
            background: #23262f;
            border-radius: 10px;
            box-shadow: 0 1px 4px #0002;
            transition: box-shadow 0.2s;
        }
        tr:hover {
            box-shadow: 0 4px 16px #0004;
        }
        td {
            border-bottom: 1px solid #232b3a;
            font-size: 1.08em;
        }
        tr:last-child td {
            border-bottom: none;
        }
        a.button, button {
            background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%);
            color: #fff;
            padding: 0.6em 1.2em;
            border-radius: 7px;
            text-decoration: none;
            font-weight: 600;
            border: none;
            cursor: pointer;
            box-shadow: 0 2px 8px #2563eb33;
            transition: background 0.2s, box-shadow 0.2s;
            outline: none;
        }
        a.button:hover, button:hover {
            background: linear-gradient(90deg, #1e40af 0%, #2563eb 100%);
            box-shadow: 0 4px 16px #2563eb55;
        }
        .flash {
            padding: 1em;
            margin-bottom: 1.2em;
            border-radius: 7px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .flash-success {
            background: #22c55e33;
            color: #22c55e;
        }
        .flash-danger {
            background: #ef444433;
            color: #ef4444;
        }
        @media (max-width: 600px) {
            .container {
                padding: 1em 0.3em 1.5em 0.3em;
            }
            th, td {
                padding: 0.7em 0.2em;
                font-size: 0.98em;
            }
            h1 {
                font-size: 1.3em;
            }
        }
        footer {
            text-align: center;
            color: #64748b;
            font-size: 0.95em;
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
                <a class="button" href="/logout">Logout</a>
            {% else %}
                <a class="button" href="/login">Login</a>
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
        <h2 style="color:#22c55e; text-align:center; margin-top:1em;">Due Bosses</h2>
        <table>
            <tr>
                <th>Boss</th>
                <th>Last Reset By</th>
                <th>Next Spawn</th>
                <th>Window End</th>
                <th>Action</th>
            </tr>
            {% for boss in due_bosses %}
            <tr style="background:#1e293b;">
                <td>{{ boss.name }}</td>
                <td>{{ boss.last_user }}</td>
                <td><span class="respawn-timer" data-seconds="{{ boss.respawn_seconds }}">{{ boss.respawn }}</span></td>
                <td><span class="window-timer" data-seconds="{{ boss.window_seconds }}">{{ boss.window_end }}</span></td>
                <td>
                    {% if username %}
                        <a class="button" href="/reset/{{ boss.name }}">Reset</a>
                    {% else %}
                        <a class="button" href="/login">Login to Reset</a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        <h2 style="color:#7dd3fc; text-align:center; margin-top:2em;">Upcoming Bosses</h2>
        <table>
            <tr>
                <th>Boss</th>
                <th>Last Reset By</th>
                <th>Next Spawn</th>
                <th>Window End</th>
                <th>Action</th>
            </tr>
            {% for boss in bosses %}
            <tr>
                <td>{{ boss.name }}</td>
                <td>{{ boss.last_user }}</td>
                <td><span class="respawn-timer" data-seconds="{{ boss.respawn_seconds }}">{{ boss.respawn }}</span></td>
                <td><span class="window-timer" data-seconds="{{ boss.window_seconds }}">{{ boss.window_end }}</span></td>
                <td>
                    {% if username %}
                        <a class="button" href="/reset/{{ boss.name }}">Reset</a>
                    {% else %}
                        <a class="button" href="/login">Login to Reset</a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <footer>
        &copy; {{ now().year }} Axiom Clan Timers &mdash; Powered by Flask
    </footer>
    <script>
    function formatCountdown(seconds) {
        if (seconds === null || seconds === '' || isNaN(seconds)) return '';
        if (seconds <= 0) return 'Ready!';
        let h = Math.floor(seconds / 3600);
        let m = Math.floor((seconds % 3600) / 60);
        let s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    function updateTimers() {
        document.querySelectorAll('.respawn-timer').forEach(function(el) {
            let seconds = parseInt(el.getAttribute('data-seconds'));
            if (isNaN(seconds) || el.innerText === 'N/A') return;
            if (seconds > 0) {
                el.innerText = formatCountdown(seconds);
                el.setAttribute('data-seconds', seconds - 1);
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
                    let wSeconds = parseInt(windowEl.getAttribute('data-seconds'));
                    if (!isNaN(wSeconds) && wSeconds > 0) {
                        windowEl.innerText = formatCountdown(wSeconds);
                        windowEl.setAttribute('data-seconds', wSeconds - 1);
                    } else if (!isNaN(wSeconds) && wSeconds <= 0) {
                        windowEl.innerText = '';
                    }
                }
            }
        });
        // Also update window timers that are already running
        document.querySelectorAll('.window-timer').forEach(function(el) {
            let respawnEl = el.parentElement.parentElement.querySelector('.respawn-timer');
            if (respawnEl && respawnEl.innerText !== 'Ready!') return; // Only update if respawn is ready
            let seconds = parseInt(el.getAttribute('data-seconds'));
            if (isNaN(seconds) || seconds === '' || el.innerText === 'N/A') return;
            if (seconds > 0) {
                el.innerText = formatCountdown(seconds);
                el.setAttribute('data-seconds', seconds - 1);
            } else {
                el.innerText = '';
            }
        });
    }
    setInterval(updateTimers, 1000);
    window.onload = updateTimers;
    </script>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Axiom MMO Timers</title>
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

if __name__ == '__main__':
    app.run(debug=True) 