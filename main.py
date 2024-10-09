from flask import Flask, render_template, request, send_file
import fitz  # PyMuPDF para manejar PDFs
import qrcode
import os
from io import BytesIO

app = Flask(__name__)

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

# Función para generar el código QR
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
    return img

# Función para superponer PDFs y agregar dos QRs en memoria
def overlay_pdf_on_background(pdf_file, output_stream):
    try:
        # Leer el PDF subido en memoria
        selected_pdf = fitz.open(stream=pdf_file.read(), filetype="pdf")
        background_pdf = fitz.open(BACKGROUND_PDF_PATH)
        output_pdf = fitz.open()

        for page_num in range(len(background_pdf)):
            background_page = background_pdf.load_page(page_num)
            new_page = output_pdf.new_page(width=background_page.rect.width, height=background_page.rect.height)
            new_page.show_pdf_page(new_page.rect, background_pdf, page_num)

            if page_num < len(selected_pdf):
                selected_page = selected_pdf.load_page(page_num)
                new_page.show_pdf_page(new_page.rect, selected_pdf, page_num)

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

        qr_img = generate_qr_code(filename)
        qr_img = qr_img.resize((60, 60))

        qr_img_path = "temp_qr.png"
        qr_img.save(qr_img_path)

        # Si hay más de una página, insertamos los QRs en la segunda página
        if len(output_pdf) > 1:
            second_page = output_pdf.load_page(1)

            # Primer QR (parte superior)
            qr_rect = fitz.Rect(34, 24, 95, 88)
            second_page.insert_image(qr_rect, filename=qr_img_path)

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
            second_page.insert_image(qr_rect_bottom_left, filename=qr_img_path)

        # Guardar el archivo en el stream de salida (en memoria)
        output_pdf.save(output_stream)
        output_pdf.close()
        selected_pdf.close()
        background_pdf.close()

    except Exception as e:
        print(f"Error overlaying PDFs: {e}")

# Ruta principal para la página de inicio
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para procesar el enmarcado de PDFs sin guardar en disco
@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    if 'pdf_file' not in request.files:
        return 'No file uploaded', 400

    pdf_file = request.files['pdf_file']
    if pdf_file.filename == '':
        return 'No selected file', 400

    # Crear un objeto BytesIO para mantener el archivo generado en memoria
    output_stream = BytesIO()

    # Generar el PDF enmarcado directamente en memoria
    overlay_pdf_on_background(pdf_file, output_stream)

    # Enviar el archivo generado como una descarga
    output_stream.seek(0)  # Reiniciar el puntero al inicio del stream
    return send_file(output_stream, as_attachment=True, download_name=f"marcado_{pdf_file.filename}", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
