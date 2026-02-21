# src/tenancy.py

from flask import g, session, request, abort
from flask_login import current_user

from src.repositories.tenancy_repository import (
    resolve_default_clinic_id,
    get_user_membership,
)


def init_tenancy(app):

    @app.before_request
    def attach_clinic_context():

        # ignora login e arquivos estáticos
        if request.path.startswith("/static") or request.path == "/login":
            return

        if not current_user.is_authenticated:
            return

        user_id = int(current_user.id)

        clinic_id = session.get("active_clinic_id")

        # Se não houver clínica ativa na sessão
        if clinic_id is None:
            clinic_id = resolve_default_clinic_id(user_id)

            if clinic_id is None:
                abort(403)

            session["active_clinic_id"] = clinic_id

        membership = get_user_membership(user_id, clinic_id)

        if membership is None:
            abort(403)

        # Anexa no contexto global da request
        g.clinic_id = membership["clinic_id"]
        g.clinic_role = membership["role"]