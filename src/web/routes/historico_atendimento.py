from flask import Blueprint, render_template
from src.api.auth import role_required
from repositories import message_repository

historico_bp = Blueprint('historico', __name__, template_folder='templates')


@historico_bp.route('/historico', methods=['GET'])
@role_required('Admin', 'Medico', 'Atendente')
def historico():
    try:
        message_repository.ensure_message_tables()
        messages = message_repository.list_messages()
        return render_template('historico_atendimento.html', messages=messages)
    except Exception as e:
        return f'Erro ao acessar o histórico: {e}', 500


if __name__ == '__main__':
    from flask import Flask

    app = Flask(__name__, template_folder='templates')
    app.register_blueprint(historico_bp)
    app.run(port=5008, debug=True)
