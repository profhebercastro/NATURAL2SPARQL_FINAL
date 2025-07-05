#!/bin/bash

echo "Iniciando o serviço Java..."
java -jar app.jar &

sleep 10

echo "Iniciando o serviço Python com Gunicorn..."
# Muda o diretório para a nova pasta de recursos e chama o script
gunicorn --bind 0.0.0.0:5000 --workers 2 --chdir /app/resources nlp_controller:app