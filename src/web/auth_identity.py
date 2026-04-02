from flask_login import UserMixin


class AppUser(UserMixin):
    def __init__(self, user_id: int, username: str, role: str):
        self.id = str(user_id)
        self.username = username
        self.role = role
        self.global_role = role
