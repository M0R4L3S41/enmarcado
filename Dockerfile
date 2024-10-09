# Usa una imagen base de Python
FROM python:3.9

# Instala las dependencias del sistema necesarias para compilar PyMuPDF
RUN apt-get update && apt-get install -y \
    gcc \
    libmupdf-dev \
    mupdf-tools \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    make \
    cmake \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar los archivos del proyecto al contenedor
COPY . /app

# Instalar las dependencias de Python desde el requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Exponer el puerto que usará Flask
EXPOSE 5000

# Comando para ejecutar la aplicación Flask usando gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "main:app"]
