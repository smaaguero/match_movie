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
git clone https://github.com/smaaguero/match_movie
chown -R ec2-user:ec2-user match_movie

# Entrar al directorio del proyecto
cd match_movie

# Obtener la contraseña de la BD desde Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id match-movie/db-password --query SecretString --output text --region us-east-1)

# Crear el fichero .env
cat > .env <<ENV
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@match-movie-db-instance.c7aswmkqsgul.us-east-1.rds.amazonaws.com:5432/matchmoviedb
ENV

# Construir y lanzar los contenedores
docker-compose up -d
