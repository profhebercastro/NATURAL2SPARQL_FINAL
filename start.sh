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
# 1. Navega para o diretório do serviço de NLP.
#    Isso é essencial para que o script encontre seus arquivos .json e .txt
cd /app/nlp

# 2. Executa o Gunicorn a partir do diretório correto.
#    O Gunicorn agora encontrará 'nlp_controller.py' sem problemas.
#    'exec' faz com que este se torne o processo principal do container.
exec gunicorn --bind 0.0.0.0:5000 nlp_controller:app