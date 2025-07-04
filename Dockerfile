# Usa una imagen base de Python
FROM python:3.11-slim

# Establece el directorio de trabajo en /app
WORKDIR /app

# Instala poetry
RUN pip install poetry

# Copia los archivos de dependencias de poetry
COPY pyproject.toml poetry.lock* ./

# Instala las dependencias del proyecto con poetry
RUN poetry config virtualenvs.create false && poetry install --without dev --no-root

# Copia el resto de los archivos de la aplicación al contenedor
COPY . .

# Expone el puerto en el que corre la aplicación
EXPOSE 5001

# Comando para correr la aplicación
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "app:app"]