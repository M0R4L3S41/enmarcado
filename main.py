from flask import Flask, render_template, request, send_file, jsonify
import fitz  # PyMuPDF para manejar PDFs
import qrcode
import os
from io import BytesIO
from PIL import Image  # Importar la biblioteca Pillow
from datetime import datetime  # Para manejar fechas y horas
import pytz  # Para manejar zonas horarias

app = Flask(__name__)

# Configuración para el tamaño máximo de archivos (16 MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Ruta al archivo de fondo
BACKGROUND_PDF_PATH = "static/marcoparaactas.pdf"
MARCOS_FOLDER = "static/marcostraceros"

# Diccionario de abreviaturas y estados
ESTADOS = {
    "AS": "AGUASCALIENTES", "BC": "BAJA CALIFORNIA", "BS": "BAJA CALIFORNIA SUR", "CC": "CAMPECHE",
    "CL": "COAHUILA", "CM": "COLIMA", "CS": "CHIAPAS", "CH": "CHIHUAHUA", "DF": "DISTRITO FEDERAL",
    "DG": "DURANGO", "GT": "GUANAJUATO", "GR": "GUERRERO", "HG": "HIDALGO", "JC": "JALISCO",
    "MC": "MÉXICO", "MN": "MICHOACÁN", "MS": "MORELOS", "NT": "NAYARIT", "NL": "NUEVO LEÓN",
    "OC": "OAXACA", "PL": "PUEBLA", "QT": "QUERÉTARO", "QR": "QUINTANA ROO", "SP": "SAN LUIS POTOSÍ",
    "SL": "SINALOA", "SR": "SONORA", "TC": "TABASCO", "TS": "TAMAULIPAS", "TL": "TLAXCALA",
    "VZ": "VERACRUZ", "YN": "YUCATÁN", "ZS": "ZACATECAS", "NE": "NACIDO EN EL EXTRANJERO"
}

# Definir la zona horaria de México
mexico_timezone = pytz.timezone('America/Mexico_City')

def is_within_working_hours():
    # Obtener la hora actual en UTC y convertirla a la zona horaria de México
    now = datetime.now(pytz.utc).astimezone(mexico_timezone)
    
    # Imprimir la hora actual del servidor en la zona horaria de México
    print(f"Hora actual del servidor (Hora México): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # Verificar si es un día entre lunes (0) y viernes (4)
    if now.weekday() > 4:
        return False  # Es sábado o domingo, no está disponible

    # Definir el horario de trabajo (9 AM a 5 PM)
    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=17, minute=0, second=0, microsecond=0)

    # Verificar si la hora actual está dentro del horario permitido
    return start_time <= now <= end_time

# Función para generar el código QR en memoria (BytesIO)
def generate_qr_code(text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=0,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    # Convertir la imagen de QR a formato PNG utilizando Pillow
    img_byte_array = BytesIO()
    img.save(img_byte_array, format="PNG")  # Guardar en BytesIO como PNG
    img_byte_array.seek(0)  # Mover el puntero al inicio

    # Crear un Pixmap de PyMuPDF desde el stream de bytes PNG
    qr_img_fitz = fitz.Pixmap(img_byte_array)  # Cargar imagen PNG directamente en Pixmap
    
    return qr_img_fitz

# Función para superponer PDFs y agregar dos QRs en memoria
def overlay_pdf_on_background(pdf_file, output_stream):
    try:
        # Verificar si el archivo de fondo existe
        if not os.path.exists(BACKGROUND_PDF_PATH):
            return False, f"Error: El archivo de fondo '{BACKGROUND_PDF_PATH}' no existe."

        # Leer el PDF subido en memoria
        try:
            selected_pdf = fitz.open(stream=pdf_file.read(), filetype="pdf")
        except Exception as e:
            return False, f"Error al cargar el archivo PDF: {e}"

        # Verificar que el PDF cargado no esté vacío
        if len(selected_pdf) == 0:
            return False, "Error: El PDF cargado está vacío."

        background_pdf = fitz.open(BACKGROUND_PDF_PATH)
        output_pdf = fitz.open()

        for page_num in range(len(background_pdf)):
            background_page = background_pdf.load_page(page_num)
            new_page = output_pdf.new_page(width=background_page.rect.width, height=background_page.rect.height)
            new_page.show_pdf_page(new_page.rect, background_pdf, page_num)

            if page_num < len(selected_pdf):
                selected_page = selected_pdf.load_page(page_num)
                new_page.show_pdf_page(new_page.rect, selected_pdf, page_num)

        # Procesar el nombre del archivo para generar el QR y manejar el PDF del estado correspondiente
        filename = os.path.basename(pdf_file.filename)
        state_abbr = filename[11:13].upper()

        if state_abbr in ESTADOS:
            state_pdf_path = os.path.join(MARCOS_FOLDER, f"{state_abbr}.pdf")
            if os.path.exists(state_pdf_path):
                state_pdf = fitz.open(state_pdf_path)
                for state_page_num in range(len(state_pdf)):
                    new_page = output_pdf.new_page(width=state_pdf[state_page_num].rect.width, height=state_pdf[state_page_num].rect.height)
                    new_page.show_pdf_page(new_page.rect, state_pdf, state_page_num)
                state_pdf.close()

        # Generar y colocar los QR Codes en memoria
        qr_img = generate_qr_code(filename)

        # Si hay más de una página, insertar los QRs en la segunda página
        if len(output_pdf) > 1:
            second_page = output_pdf.load_page(1)

            # Primer QR (parte superior)
            qr_rect = fitz.Rect(34, 24, 95, 88)
            second_page.insert_image(qr_rect, pixmap=qr_img)

            first_18_chars = filename[:18]
            second_page.insert_text((qr_rect.x0 - 7, qr_rect.y1 + 10), first_18_chars, fontsize=7, color=(0.5, 0.5, 0.5))

            # Segundo QR (parte inferior izquierda)
            page_height = second_page.rect.height
            qr_size_small = 17 * 2.83465  # Tamaño del segundo QR en puntos
            move_up = 5.33 * 2.83465  # Ajuste para mover el QR hacia arriba
            move_right = 4.26 * 2.83465  # Ajuste para mover el QR hacia la derecha

            qr_rect_bottom_left = fitz.Rect(
                20 + move_right,
                (page_height - qr_size_small - 10) - move_up,
                (20 + qr_size_small + move_right),
                (page_height - 10) - move_up
            )
            second_page.insert_image(qr_rect_bottom_left, pixmap=qr_img)

        # Guardar el archivo en el stream de salida (en memoria)
        output_pdf.save(output_stream)
        output_pdf.close()
        selected_pdf.close()
        background_pdf.close()
        return True, "PDF generado correctamente."

    except Exception as e:
        print(f"Error overlaying PDFs: {e}")
        return False, f"Error al generar el PDF: {e}"

# Ruta principal para la página de inicio
@app.route('/')
def index():
    if not is_within_working_hours():
        return "El servicio no está disponible fuera del horario de 9 AM a 5 PM.", 403
    return render_template('index.html')

# Ruta para procesar el enmarcado de PDFs sin guardar en disco
@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    if not is_within_working_hours():
        return "El servicio no está disponible fuera del horario de 9 AM a 5 PM.", 403
    try:
        if 'pdf_file' not in request.files:
            print("No file in request.files")
            return 'No file uploaded', 400

        pdf_file = request.files['pdf_file']
        print(f"Archivo recibido: {pdf_file.filename}")
        
        if pdf_file.filename == '':
            print("No file selected")
            return 'No selected file', 400

        # Crear un objeto BytesIO para mantener el archivo generado en memoria
        output_stream = BytesIO()

        # Generar el PDF enmarcado directamente en memoria
        success, message = overlay_pdf_on_background(pdf_file, output_stream)
        if not success:
            print(f"Error generando el PDF: {message}")
            return message, 500

        # Enviar el archivo generado como una descarga
        output_stream.seek(0)  # Reiniciar el puntero al inicio del stream
        return send_file(output_stream, as_attachment=True, download_name=f"marcado_{pdf_file.filename}", mimetype='application/pdf')

    except Exception as e:
        print(f"Error procesando PDF: {e}")
        return 'Error procesando archivo PDF', 500

# Configuración del servidor para producción o local
if __name__ == '__main__':
    app.run(debug=os.getenv("FLASK_DEBUG", False), host='0.0.0.0', port=os.getenv("PORT", 5000))
