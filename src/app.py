import logging
import time

from flask import Flask, g, render_template, request

from config import SECRET_KEY
from historico_atendimento import historico_bp
from realtime_notifications import realtime_bp, socketio
from scheduling_chain import scheduling_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY
socketio.init_app(app)

app.register_blueprint(realtime_bp)
app.register_blueprint(scheduling_bp)
app.register_blueprint(historico_bp)


@app.before_request
def before_request():
    g._request_start = time.time()


@app.after_request
def after_request(response):
    elapsed_ms = int((time.time() - g.get('_request_start', time.time())) * 1000)
    logging.info(
        'request path=%s method=%s status=%s elapsed_ms=%s',
        request.path,
        request.method,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
