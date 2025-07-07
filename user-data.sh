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

# Clonar el repositorio con la URL correcta como ec2-user
su - ec2-user -c "git clone https://github.com/smaaguero/match_movie.git"

# Entrar al directorio del proyecto
cd /home/ec2-user/match_movie

# --- SECCIÓN DE SECRETOS ---
AWS_REGION="us-east-1"
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id match-movie/db-password --query SecretString --output text --region $AWS_REGION)
FLASK_KEY=$(aws secretsmanager get-secret-value --secret-id match-movie/flask-key --query SecretString --output text --region $AWS_REGION)
TMDB_KEY=$(aws secretsmanager get-secret-value --secret-id match-movie/tmdb-api-key --query SecretString --output text --region $AWS_REGION)

echo "$FLASK_KEY" > flask_secret.txt
echo "$TMDB_KEY" > tmdb_api_key.txt

cat > .env <<ENV
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@match-movie-db-instance.c7aswmkqsgul.us-east-1.rds.amazonaws.com:5432/matchmoviedb
ENV
# --- FIN DE LA SECCIÓN DE SECRETOS ---

# Corregir permisos de los ficheros creados por root
chown ec2-user:ec2-user flask_secret.txt tmdb_api_key.txt .env

# Construir y lanzar los contenedores COMO EC2-USER
su - ec2-user -c "cd /home/ec2-user/match_movie && docker-compose up -d"
