#!/bin/bash
# Actualizar el sistema e instalar paquetes
yum update -y
yum install -y docker git
amazon-linux-extras install -y docker

# Iniciar Docker y añadir ec2-user al grupo de docker
service docker start
usermod -a -G docker ec2-user

# Instalar Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clonar el repositorio
cd /home/ec2-user
git clone https://github.com/saguero/match_movie.git
chown -R ec2-user:ec2-user match_movie

# Entrar al directorio del proyecto
cd match_movie

# --- SECCIÓN DE SECRETOS MEJORADA ---
# Definir la región para evitar problemas
AWS_REGION="us-east-1"

# Obtener todos los secretos de AWS Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id match-movie/db-password --query SecretString --output text --region $AWS_REGION)
FLASK_KEY=$(aws secretsmanager get-secret-value --secret-id match-movie/flask-key --query SecretString --output text --region $AWS_REGION)
TMDB_KEY=$(aws secretsmanager get-secret-value --secret-id match-movie/tmdb-api-key --query SecretString --output text --region $AWS_REGION)

# Crear los ficheros de secretos que la aplicación espera
echo $FLASK_KEY > flask_secret.txt
echo $TMDB_KEY > tmdb_api_key.txt

# Crear el fichero .env para la base de datos
cat > .env <<ENV
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@match-movie-db-instance.c7aswmkqsgul.us-east-1.rds.amazonaws.com:5432/matchmoviedb
ENV
# --- FIN DE LA SECCIÓN DE SECRETOS ---

# Construir y lanzar los contenedores
docker-compose up -d