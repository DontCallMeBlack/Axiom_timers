from flask import Flask, render_template_string, request, redirect, url_for, flash
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

@app.route('/', methods=['GET'])
def index():
    timers = load_timers()
    now = datetime.utcnow()
    boss_infos = []
    for boss in BOSSES:
        last_kill = timers.get(boss['name'])
        if last_kill:
            last_kill_dt = datetime.fromisoformat(last_kill)
            respawn = last_kill_dt + timedelta(minutes=boss['respawn_minutes'])
            window_end = respawn + timedelta(minutes=boss['window_minutes'])
        else:
            respawn = window_end = None
        boss_infos.append({
            'name': boss['name'],
            'respawn': respawn.strftime('%Y-%m-%d %H:%M UTC') if respawn else 'N/A',
            'window_end': window_end.strftime('%Y-%m-%d %H:%M UTC') if window_end else 'N/A',
            'last_kill': last_kill_dt.strftime('%Y-%m-%d %H:%M UTC') if last_kill else 'N/A',
        })
    return render_template_string(TEMPLATE, bosses=boss_infos)

@app.route('/reset/<boss_name>', methods=['GET', 'POST'])
def reset(boss_name):
    boss = get_boss_by_name(boss_name)
    if not boss:
        flash('Boss not found.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if USERS.get(username) != password:
            flash('Invalid username or password.', 'danger')
            return redirect(request.url)
        kill_time = request.form.get('kill_time')
        try:
            kill_dt = datetime.strptime(kill_time, '%Y-%m-%dT%H:%M')
        except Exception:
            flash('Invalid kill time format.', 'danger')
            return redirect(request.url)
        timers = load_timers()
        timers[boss_name] = kill_dt.isoformat()
        save_timers(timers)
        flash(f'{boss_name} timer reset!', 'success')
        return redirect(url_for('index'))
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M')
    return render_template_string(RESET_TEMPLATE, boss=boss, now=now)

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axiom MMO Timers</title>
    <style>
        body { font-family: Arial, sans-serif; background: #181a20; color: #eee; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 10px; box-shadow: 0 2px 8px #0008; }
        h1 { text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 1em; }
        th, td { padding: 0.7em; text-align: center; border-bottom: 1px solid #333; }
        th { background: #2d303a; }
        tr:last-child td { border-bottom: none; }
        a.button { background: #3b82f6; color: #fff; padding: 0.5em 1em; border-radius: 5px; text-decoration: none; }
        a.button:hover { background: #2563eb; }
        .flash { padding: 1em; margin-bottom: 1em; border-radius: 5px; }
        .flash-success { background: #22c55e; color: #fff; }
        .flash-danger { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Axiom MMO Timers</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <table>
            <tr>
                <th>Boss</th>
                <th>Last Kill</th>
                <th>Next Spawn</th>
                <th>Window End</th>
                <th>Action</th>
            </tr>
            {% for boss in bosses %}
            <tr>
                <td>{{ boss.name }}</td>
                <td>{{ boss.last_kill }}</td>
                <td>{{ boss.respawn }}</td>
                <td>{{ boss.window_end }}</td>
                <td><a class="button" href="/reset/{{ boss.name }}">Reset</a></td>
            </tr>
            {% endfor %}
        </table>
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
    <style>
        body { font-family: Arial, sans-serif; background: #181a20; color: #eee; margin: 0; padding: 0; }
        .container { max-width: 400px; margin: 40px auto; background: #23262f; padding: 2em; border-radius: 10px; box-shadow: 0 2px 8px #0008; }
        h2 { text-align: center; }
        form { display: flex; flex-direction: column; gap: 1em; }
        label { font-weight: bold; }
        input, select { padding: 0.5em; border-radius: 5px; border: none; }
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
        <h2>Reset {{ boss.name }} Timer</h2>
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
            <label for="kill_time">Kill Time (UTC):</label>
            <input type="datetime-local" name="kill_time" id="kill_time" value="{{ now }}" required>
            <button type="submit">Reset Timer</button>
        </form>
        <p><a href="/">Back to Timers</a></p>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True) 