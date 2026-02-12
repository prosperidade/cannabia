from flask import Blueprint, redirect, render_template, request, url_for
from src.web.routes.auth import generate_csrf_token, role_required, validate_csrf_from_form
from src.services.appointment_service import (
    create_appointment_from_form,
    list_appointments,
)


scheduling_bp = Blueprint('scheduling', __name__, template_folder='templates')


@scheduling_bp.route('/scheduling', methods=['GET', 'POST'])
@role_required('Admin', 'Medico', 'Atendente')
def scheduling():
    if request.method == 'POST':
        if not validate_csrf_from_form():
            return 'CSRF inválido.', 400

        patient_name = request.form.get('patient_name')
        appointment_date = request.form.get('appointment_date')
        try:
            create_appointment_from_form(patient_name, appointment_date)
            return redirect(url_for('scheduling.scheduling'))
        except ValueError as exc:
            return str(exc), 400

    appointments = list_appointments()

    return render_template('scheduling_dashboard.html', appointments=appointments)

    return render_template('scheduling_dashboard.html', appointments=appointments, csrf_token=generate_csrf_token())



if __name__ == '__main__':
    from flask import Flask

    app = Flask(__name__, template_folder='templates')
    app.register_blueprint(scheduling_bp)
    app.run(port=5007, debug=True)
