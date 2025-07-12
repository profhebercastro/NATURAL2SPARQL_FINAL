#!/bin/bash

# Inicia o serviço Python (Flask) com Gunicorn em segundo plano
# Ele ficará escutando na porta 5000
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app &

# Aguarda 5 segundos para garantir que o serviço Python esteja pronto
# Isso evita que o Java tente se comunicar antes do Python estar no ar
sleep 5

# Inicia o serviço principal (Java/Spring Boot) em PRIMEIRO PLANO
# Este será o processo principal do container. Quando ele terminar, o container para.
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta 8080 ---"
java -jar app.jar