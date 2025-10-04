from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quiz-buzzer-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store game state
players = {}  # {sid: {"name": str, "buzz_time": None or datetime}}
buzz_order = []  # List of (name, sid) in order of buzzing
is_locked = False

# HTML Templates
PLAYER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Quiz Buzzer - Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        #joinSection, #gameSection {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 500px;
            width: 100%;
        }
        h1 { color: #667eea; margin-bottom: 20px; font-size: 2em; }
        input {
            width: 100%;
            padding: 15px;
            font-size: 18px;
            border: 2px solid #ddd;
            border-radius: 10px;
            margin-bottom: 20px;
            transition: border 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 15px 30px;
            font-size: 20px;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        #joinBtn {
            background: #667eea;
            color: white;
        }
        #joinBtn:hover { background: #5568d3; }
        #buzzBtn {
            background: #f43f5e;
            color: white;
            font-size: 48px;
            padding: 80px 40px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(244, 63, 94, 0.4);
        }
        #buzzBtn:hover:not(:disabled) {
            background: #e11d48;
            transform: scale(1.05);
        }
        #buzzBtn:active:not(:disabled) {
            transform: scale(0.95);
        }
        #buzzBtn:disabled {
            background: #ccc;
            cursor: not-allowed;
            box-shadow: none;
        }
        .status {
            margin-top: 30px;
            padding: 20px;
            border-radius: 10px;
            font-size: 20px;
            font-weight: bold;
        }
        .status.waiting {
            background: #e0e7ff;
            color: #4c1d95;
        }
        .status.buzzed {
            background: #fef3c7;
            color: #78350f;
        }
        .status.winner {
            background: #d1fae5;
            color: #065f46;
            animation: pulse 1s infinite;
        }
        .status.locked {
            background: #fee2e2;
            color: #991b1b;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .player-name {
            margin-top: 20px;
            color: #667eea;
            font-size: 24px;
            font-weight: bold;
        }
        #gameSection { display: none; }
    </style>
</head>
<body>
    <div id="joinSection">
        <h1>🎯 Quiz Buzzer</h1>
        <input type="text" id="playerName" placeholder="Enter your name" maxlength="30">
        <button id="joinBtn" onclick="joinGame()">Join Game</button>
    </div>

    <div id="gameSection">
        <h1>🎯 Quiz Buzzer</h1>
        <div class="player-name" id="playerNameDisplay"></div>
        <button id="buzzBtn" onclick="buzz()">BUZZ!</button>
        <div id="status" class="status waiting">Ready to buzz...</div>
    </div>

    <script>
        const socket = io();
        let playerName = '';
        let hasBuzzed = false;

        function joinGame() {
            playerName = document.getElementById('playerName').value.trim();
            if (!playerName) {
                alert('Please enter your name!');
                return;
            }
            socket.emit('join', { name: playerName });
        }

        socket.on('joined', (data) => {
            document.getElementById('joinSection').style.display = 'none';
            document.getElementById('gameSection').style.display = 'block';
            document.getElementById('playerNameDisplay').textContent = playerName;
        });

        function buzz() {
            if (!hasBuzzed) {
                socket.emit('buzz', { name: playerName });
                hasBuzzed = true;
            }
        }

        socket.on('buzz_result', (data) => {
            const btn = document.getElementById('buzzBtn');
            const status = document.getElementById('status');
            
            btn.disabled = true;

            if (data.position === 1) {
                status.className = 'status winner';
                status.textContent = '🎉 YOU BUZZED FIRST! 🎉';
            } else {
                status.className = 'status locked';
                status.textContent = `You were #${data.position}`;
            }
        });

        socket.on('locked_out', () => {
            const btn = document.getElementById('buzzBtn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            status.className = 'status locked';
            status.textContent = 'Someone else buzzed first!';
        });

        socket.on('reset', () => {
            const btn = document.getElementById('buzzBtn');
            const status = document.getElementById('status');
            
            btn.disabled = false;
            status.className = 'status waiting';
            status.textContent = 'Ready to buzz...';
            hasBuzzed = false;
        });

        socket.on('error', (data) => {
            alert(data.message);
        });
    </script>
</body>
</html>
"""

HOST_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Quiz Buzzer - Host</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 3em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .panel {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h2 {
            color: #1e3a8a;
            margin-bottom: 20px;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 10px;
        }
        .players-list {
            display: grid;
            gap: 10px;
        }
        .player-item {
            padding: 15px;
            background: #f1f5f9;
            border-radius: 8px;
            border-left: 4px solid #94a3b8;
            font-size: 18px;
        }
        .player-item.online {
            border-left-color: #22c55e;
        }
        .buzz-order {
            display: grid;
            gap: 15px;
            margin-top: 20px;
        }
        .buzz-item {
            padding: 20px;
            border-radius: 10px;
            font-size: 20px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .buzz-item.first {
            background: #22c55e;
            color: white;
            font-size: 28px;
            animation: winner 1s ease-in-out infinite;
        }
        .buzz-item.second {
            background: #fbbf24;
            color: #78350f;
        }
        .buzz-item.third {
            background: #fb923c;
            color: white;
        }
        .buzz-item.other {
            background: #e2e8f0;
            color: #475569;
        }
        @keyframes winner {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        .position {
            background: rgba(0,0,0,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 18px;
        }
        #resetBtn {
            width: 100%;
            padding: 20px;
            font-size: 24px;
            font-weight: bold;
            background: #ef4444;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        #resetBtn:hover {
            background: #dc2626;
            transform: scale(1.02);
        }
        #resetBtn:active {
            transform: scale(0.98);
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
            font-size: 18px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-box {
            background: #f1f5f9;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            color: #1e3a8a;
        }
        .stat-label {
            color: #64748b;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Quiz Buzzer - Host Control</h1>
        
        <div class="panel">
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number" id="playerCount">0</div>
                    <div class="stat-label">Connected Players</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" id="buzzCount">0</div>
                    <div class="stat-label">Players Buzzed</div>
                </div>
            </div>
            <button id="resetBtn" onclick="reset()">🔄 RESET BUZZER</button>
        </div>

        <div class="panel">
            <h2>📋 Connected Players</h2>
            <div id="playersList" class="players-list">
                <div class="empty-state">Waiting for players to join...</div>
            </div>
        </div>

        <div class="panel">
            <h2>⚡ Buzz Order</h2>
            <div id="buzzOrder" class="buzz-order">
                <div class="empty-state">No buzzes yet...</div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();

        socket.emit('join_host');

        socket.on('state_update', (data) => {
            updatePlayers(data.players);
            updateBuzzOrder(data.buzz_order);
            updateStats(data.players.length, data.buzz_order.length);
        });

        function updatePlayers(players) {
            const list = document.getElementById('playersList');
            if (players.length === 0) {
                list.innerHTML = '<div class="empty-state">Waiting for players to join...</div>';
                return;
            }
            
            list.innerHTML = players.map(player => 
                `<div class="player-item online">👤 ${player}</div>`
            ).join('');
        }

        function updateBuzzOrder(buzzOrder) {
            const list = document.getElementById('buzzOrder');
            if (buzzOrder.length === 0) {
                list.innerHTML = '<div class="empty-state">No buzzes yet...</div>';
                return;
            }

            const classes = ['first', 'second', 'third'];
            list.innerHTML = buzzOrder.map((name, index) => {
                const className = classes[index] || 'other';
                const medals = ['🥇', '🥈', '🥉'];
                const medal = medals[index] || '📍';
                return `
                    <div class="buzz-item ${className}">
                        <span>${medal} ${name}</span>
                        <span class="position">#${index + 1}</span>
                    </div>
                `;
            }).join('');
        }

        function updateStats(playerCount, buzzCount) {
            document.getElementById('playerCount').textContent = playerCount;
            document.getElementById('buzzCount').textContent = buzzCount;
        }

        function reset() {
            socket.emit('reset');
        }

        socket.on('error', (data) => {
            alert(data.message);
        });
    </script>
</body>
</html>
"""

@app.route('/')
def player():
    return render_template_string(PLAYER_PAGE)

@app.route('/host')
def host():
    return render_template_string(HOST_PAGE)

@socketio.on('join')
def handle_join(data):
    name = data.get('name', '').strip()
    if not name:
        emit('error', {'message': 'Name is required'})
        return
    
    sid = request.sid
    players[sid] = {"name": name, "buzz_time": None}
    emit('joined', {'name': name})
    broadcast_state()

@socketio.on('join_host')
def handle_join_host():
    broadcast_state()

@socketio.on('buzz')
def handle_buzz(data):
    global is_locked, buzz_order
    
    sid = request.sid
    if sid not in players:
        emit('error', {'message': 'Not registered'})
        return
    
    if players[sid]["buzz_time"] is not None:
        return  # Already buzzed
    
    if is_locked:
        emit('locked_out')
        return
    
    # Record buzz
    players[sid]["buzz_time"] = datetime.now()
    buzz_order.append((players[sid]["name"], sid))
    position = len(buzz_order)
    
    # Lock after first buzz
    if position == 1:
        is_locked = True
        # Notify all other players they're locked out
        for other_sid in players:
            if other_sid != sid and players[other_sid]["buzz_time"] is None:
                socketio.emit('locked_out', room=other_sid)
    
    emit('buzz_result', {'position': position})
    broadcast_state()

@socketio.on('reset')
def handle_reset():
    global is_locked, buzz_order
    
    # Reset game state
    is_locked = False
    buzz_order = []
    for sid in players:
        players[sid]["buzz_time"] = None
    
    # Notify all players
    socketio.emit('reset')
    broadcast_state()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in players:
        del players[sid]
        # Remove from buzz order if present
        global buzz_order
        buzz_order = [(name, s) for name, s in buzz_order if s != sid]
        broadcast_state()

def broadcast_state():
    player_names = [players[sid]["name"] for sid in players]
    buzz_names = [name for name, sid in buzz_order]
    
    socketio.emit('state_update', {
        'players': player_names,
        'buzz_order': buzz_names
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎯 QUIZ BUZZER SERVER STARTING")
    print("="*50)
    print("\nPlayer URL: http://localhost:5000")
    print("Host URL:   http://localhost:5000/host")
    print("\nPlayers join from their phones/devices")
    print("Host controls the game from /host page")
    print("="*50 + "\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)