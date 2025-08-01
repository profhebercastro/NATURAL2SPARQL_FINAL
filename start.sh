#!/bin/bash
# Este script inicia os dois serviços de forma simples e direta.
set -e

echo "--- Iniciando serviço principal (Java/Spring Boot) em segundo plano ---"
# O '&' no final é crucial para rodar o Java em background.
java -jar /app/app.jar &

# Adiciona uma pausa para garantir que o serviço Java esteja totalmente no ar.
echo "Aguardando o serviço Java iniciar completamente..."
sleep 15

echo "--- Iniciando serviço de NLP (Python/Flask) em primeiro plano ---"
# Navega para o diretório do serviço de NLP para que ele encontre seus dicionários.
cd /app/nlp_service

# Executa o script Python diretamente. O servidor de desenvolvimento do Flask é iniciado.
# 'exec' faz com que este se torne o processo principal do container.
exec python3 nlp_controller.py