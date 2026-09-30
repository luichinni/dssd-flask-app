from src.core.bcrypt_and_session import bcrypt
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import JSONB
from src.core.database import db
from src.core.enums import RolEnum


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)

    # Campo JSONB flexible
    # Con esto a cada rol podemos agregarle campos propios 
    datos_adicionales = db.Column(JSONB, nullable=True, default=dict)

    # Definición del campo con RolEnum
    rol = db.Column(
        db.Enum(RolEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    def set_password(self, password: str) -> None:
        """Hashea la contraseña usando la extensión Flask-Bcrypt."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verifica la contraseña usando Flask-Bcrypt."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.email} - Rol: {self.rol.value}>'