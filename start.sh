#!/bin/bash
# Este script inicia os dois serviços de forma robusta e compatível.
set -e

echo "--- Iniciando serviço principal (Java/Spring Boot) em segundo plano ---"
# O '&' no final é crucial para rodar o Java em background.
java -jar /app/app.jar &

# Adiciona uma pausa para garantir que o serviço Java esteja totalmente no ar.
echo "Aguardando o serviço Java iniciar completamente..."
sleep 15

echo "--- Iniciando serviço de NLP (Python/Flask) em primeiro plano ---"
# 1. Navega para o diretório do serviço de NLP
cd /app/nlp_service

# 2. Executa o Gunicorn a partir do diretório correto.
#    Agora ele encontrará 'nlp_controller.py' sem problemas.
exec gunicorn --bind 0.0.0.0:5000 nlp_controller:app