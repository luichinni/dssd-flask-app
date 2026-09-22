from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from src.core.models import Usuario

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
@login_required
def index():
    """Página principal (Home). Si no está logueado, Flask-Login lo manda a /login."""
    return render_template('home.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        usuario = Usuario.query.filter_by(email=email).first()

        print(f"--> Búsqueda de usuario ({email}):", usuario)

        if not usuario or not usuario.check_password(password):
            print("--> FALLO EN CHECK PASSWORD")
            flash('Correo electrónico o contraseña incorrectos.', 'error')
            return redirect(url_for('auth.login'))

        login_user(usuario)
        print("--> LOGIN EXITOSO PARA:", current_user)

        return redirect(url_for('auth.index'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))