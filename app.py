import os
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_socketio import SocketIO, emit, disconnect
from datetime import timedelta
import mysql.connector
from enmarcado import enmarcado_bp

# Instancia única de Flask
app = Flask(_name_)
app.secret_key = 'supersecretkey'
app.permanent_session_lifetime = timedelta(days=7)

# Registrar el Blueprint
app.register_blueprint(enmarcado_bp)

# Configuración de SocketIO
socketio = SocketIO(app)
def conectar_db():
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST'),
        user=os.environ.get('MYSQL_USER'),
        password=os.environ.get('MYSQL_PASSWORD'),
        database=os.environ.get('MYSQL_DATABASE')
    )
# Diccionario para almacenar los tokens de sesión activos en memoria
active_sessions = {}

# Ruta de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE nombre_usuario = %s AND contrasena = MD5(%s)", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # Generar un token de sesión único
            session_token = os.urandom(24).hex()
            
            # Forzar logout si el usuario ya está activo en otro lugar
            if user["id"] in active_sessions:
                socketio.emit('force_logout', {'message': 'Tu cuenta se inició en otro dispositivo.'}, to=active_sessions[user["id"]])
                del active_sessions[user["id"]]

            # Actualizar el token de sesión en la base de datos
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET session_token = %s WHERE id = %s", (session_token, user['id']))
            conn.commit()
            cursor.close()
            conn.close()

            # Establecer sesión en Flask y almacenar en memoria
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['nombre_usuario']
            session['session_token'] = session_token
            session['rol'] = user['rol']

            return redirect(url_for('index'))

        return render_template('login.html', error="Usuario o contraseña incorrectos.")
    return render_template('login.html')

# Ruta principal protegida
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Conectar a la base de datos y verificar el rol del usuario
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT session_token, activo, rol FROM usuarios WHERE id = %s", (session['user_id'],))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    # Verificar el estado y rol del usuario
    if not result or result['session_token'] != session.get('session_token') or result['activo'] == 0:
        session.clear()
        flash("Tu sesión ha expirado o el usuario está inactivo.")
        return redirect(url_for('login'))

    # Redirigir según el rol
    if result['rol'] == 'admin':
        return render_template('configuracion_admin.html', username=session['username'])
    else:
        return render_template('enmarcado.html', username=session['username'])

# Resto de las rutas (CRUD y lógica de sesiones) se mantienen sin cambios
# Ruta para listar usuarios (vista principal del CRUD)
@app.route('/user')
def listar_usuarios():
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('usuarios.html', users=users)

# Ruta para agregar usuario
@app.route('/user/add', methods=['GET', 'POST'])
def agregar_usuario():
    if request.method == 'POST':
        username = request.form['username']
        rol = request.form['rol']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        activo = request.form.get('activo', '0')  # Checkbox, devuelve '1' si está marcado

        # Verificar que la contraseña y su confirmación coincidan
        if password != confirm_password:
            flash("Las contraseñas no coinciden. Por favor, inténtalo de nuevo.")
            return redirect(url_for('agregar_usuario'))

        # Hashear la contraseña antes de guardarla en la base de datos
        hashed_password = os.urandom(24).hex()  # En lugar de MD5, sería mejor usar bcrypt o hashlib para mayor seguridad

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nombre_usuario, contrasena, rol, activo) VALUES (%s, MD5(%s), %s, %s)", 
                       (username, password, rol, activo))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Usuario agregado exitosamente.")
        return redirect(url_for('listar_usuarios'))

    return render_template('nuevo_usuario.html', action="Agregar Usuario")

# Ruta para editar usuario
@app.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
def editar_usuario(user_id):
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if request.method == 'POST':
        username = request.form['username']
        rol = request.form['rol']
        activo = request.form.get('activo', '0')

        cursor.execute("UPDATE usuarios SET nombre_usuario = %s, rol = %s, activo = %s WHERE id = %s", (username, rol, activo, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Usuario actualizado exitosamente.")
        return redirect(url_for('listar_usuarios'))

    cursor.close()
    conn.close()
    return render_template('nuevo_usuario.html', user=user, action="Editar Usuario")

# Ruta para eliminar usuario
@app.route('/user/delete/<int:user_id>', methods=['POST'])
def eliminar_usuario(user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Usuario eliminado exitosamente.")
    return redirect(url_for('listar_usuarios'))

# Ruta para activar/desactivar usuario
@app.route('/user/toggle/<int:user_id>')
def toggle_usuario(user_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET activo = NOT activo WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Estado del usuario actualizado.")
    return redirect(url_for('listar_usuarios'))

# Ruta de Logout
@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET session_token = NULL WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        if user_id in active_sessions:
            del active_sessions[user_id]
    session.clear()
    return redirect(url_for('login'))

# Evento de conexión a SocketIO
@socketio.on('connect')
def connect():
    user_id = session.get('user_id')
    if user_id:
        # Verificar si el usuario ya tiene una sesión activa
        if user_id in active_sessions:
            # Desconectar la sesión anterior
            socketio.emit('force_logout', {'message': 'Tu cuenta se inició en otro dispositivo.'}, to=active_sessions[user_id])
            # Eliminar la sesión anterior
            del active_sessions[user_id]

        # Registrar la nueva sesión
        active_sessions[user_id] = request.sid
    else:
        disconnect()
# Evento de desconexión a SocketIO
@socketio.on('disconnect')
def disconnect_handler():
    user_id = session.get('user_id')
    if user_id and user_id in active_sessions:
        del active_sessions[user_id]

if _name_ == '_main_':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
