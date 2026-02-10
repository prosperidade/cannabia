from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from services.appointment_service import create_appointment_from_form, list_appointments

scheduling_bp = Blueprint('scheduling', __name__, template_folder='templates')


@scheduling_bp.route('/scheduling', methods=['GET', 'POST'])
@login_required
def scheduling():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        appointment_date = request.form.get('appointment_date')
        try:
            create_appointment_from_form(patient_name, appointment_date)
            return redirect(url_for('scheduling.scheduling'))
        except ValueError as exc:
            return str(exc), 400

    appointments = list_appointments()
    return render_template('scheduling_dashboard.html', appointments=appointments)


if __name__ == '__main__':
    from flask import Flask

    app = Flask(__name__, template_folder='templates')
    app.register_blueprint(scheduling_bp)
    app.run(port=5007, debug=True)
