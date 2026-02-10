from flask import Flask, render_template, request

from auth import role_required
from repositories import message_repository

app = Flask(__name__, template_folder='templates')


@app.route('/dashboard', methods=['GET'])
@role_required('Admin', 'Medico')
def dashboard():
    sender_filter = request.args.get('sender')

    try:
        message_repository.ensure_message_tables()
        messages = message_repository.list_messages(sender_filter)
        agg_data = message_repository.aggregate_messages_by_contact()
        agg_time_data = message_repository.aggregate_messages_by_day()

        labels = [row['contact_name'] for row in agg_data]
        counts = [row['message_count'] for row in agg_data]
        line_labels = [str(row['message_date']) for row in agg_time_data]
        line_data = [row['total_messages'] for row in agg_time_data]

        return render_template(
            'dashboard.html',
            messages=messages,
            sender_filter=sender_filter,
            labels=labels,
            counts=counts,
            line_labels=line_labels,
            line_data=line_data,
        )
    except Exception as e:
        return f'Erro ao acessar o dashboard: {e}', 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)
