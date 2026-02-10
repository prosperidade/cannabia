from flask import Flask, render_template
from flask_socketio import SocketIO
from realtime_notifications import realtime_bp, socketio as rt_socketio
from scheduling_chain import scheduling_bp
from historico_atendimento import historico_bp

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Registra os Blueprints
app.register_blueprint(realtime_bp)
app.register_blueprint(scheduling_bp)
app.register_blueprint(historico_bp)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
