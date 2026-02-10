from flask import Flask

from src.api.realtime_notifications import realtime_bp

app = Flask(__name__, template_folder='templates')
app.register_blueprint(realtime_bp)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
