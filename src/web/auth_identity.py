from flask_login import UserMixin


class AppUser(UserMixin):
    """User object usado pelo Flask-Login.

    `is_clinic_admin` indica que o user e administrador do tenant,
    independente do role principal. Combina com qualquer role:
        - Medico + is_clinic_admin=True  -> medico-dono
        - AdminClinica (com is_clinic_admin=True por convencao)
        - Medico + is_clinic_admin=False -> medico assalariado
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        role: str,
        is_clinic_admin: bool = False,
    ):
        self.id = str(user_id)
        self.username = username
        self.role = role
        self.global_role = role
        self.is_clinic_admin = bool(is_clinic_admin)
