import os
from flask import Flask, render_template, request, redirect, session
import mysql.connector
from datetime import datetime, timedelta
from enmarcado import enmarcado_bp

app = Flask(__name__)
app.secret_key = 'moral3s41@@'
app.permanent_session_lifetime = timedelta(minutes=30)

# Configuración de la base de datos
def conectar_db():
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST'),
        user=os.environ.get('MYSQL_USER'),
        password=os.environ.get('MYSQL_PASSWORD'),
        database=os.environ.get('MYSQL_DATABASE')
    )

# Registrar el Blueprint del módulo de enmarcado
app.register_blueprint(enmarcado_bp)

# Ruta para el formulario de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Conectar a la base de datos
        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)

        # Verificar el usuario y la contraseña
        cursor.execute("SELECT * FROM usuarios WHERE nombre_usuario = %s AND contrasena = MD5(%s)", (username, password))
        user = cursor.fetchone()

        if user:
            cursor.execute("SELECT * FROM sesiones_activas WHERE usuario_id = %s", (user['id'],))
            sesion_activa = cursor.fetchone()

            if sesion_activa:
                return render_template('login.html', error="Usuario ya conectado en otra computadora.")

            # Registrar la sesión
            ip_usuario = request.remote_addr
            cursor.execute(
                "INSERT INTO sesiones_activas (usuario_id, ultima_ip, fecha_inicio) VALUES (%s, %s, %s)",
                (user['id'], ip_usuario, datetime.now())
            )
            conn.commit()

            session['user_id'] = user['id']
            session['username'] = user['nombre_usuario']
            return redirect('/')

        else:
            return render_template('login.html', error="Usuario o contraseña incorrectos.")

        cursor.close()
        conn.close()

    return render_template('login.html')

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sesiones_activas")
        conn.commit()
        cursor.close()
        conn.close()

    session.clear()
    return redirect('/login')

if __name__ == '__main__':
     app.run(debug=os.getenv("FLASK_DEBUG", False), host='0.0.0.0', port=os.getenv("PORT", 5001))
    
