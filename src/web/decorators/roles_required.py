from functools import wraps
from typing import Union
from flask import abort
from flask_login import current_user, login_required
from src.core.enums import RolEnum

def roles_required(*roles: Union[RolEnum, str]):
    """
    Decorador para restringir el acceso a rutas según el rol del usuario.
    Permite pasar instancias de RolEnum o strings directamente.
    
    Uso:
        @roles_required(RolEnum.OPERADOR_MUNICIPAL)
        @roles_required(RolEnum.CENTRO_COORDINADOR, RolEnum.AUDITOR)
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            # Normalizar los roles permitidos a sus valores en string
            roles_permitidos = [
                r.value if isinstance(r, RolEnum) else r 
                for r in roles
            ]
            
            # Obtener el rol del usuario actual (sea Enum o String)
            rol_usuario = (
                current_user.rol.value 
                if isinstance(current_user.rol, RolEnum) 
                else current_user.rol
            )

            # Verificar si el usuario tiene un rol autorizado
            if rol_usuario not in roles_permitidos:
                # Retorna 403 HTTP Access Denied
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator