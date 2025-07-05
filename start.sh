#!/bin/bash

# Inicia o serviço Java em segundo plano
echo "Iniciando o serviço Java..."
java -jar app.jar &

# Espera para o Java começar
sleep 15

# Inicia o serviço Python
echo "Iniciando o serviço Python com Gunicorn..."
# Muda para a pasta 'nlp' e executa o controller
gunicorn --bind 0.0.0.0:5000 --workers 2 --chdir /app/nlp nlp_controller:app