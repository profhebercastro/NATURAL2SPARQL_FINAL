#!/bin/bash

# Define a porta do serviço Java usando a variável de ambiente do Render,
# com um fallback para 10000 se não estiver definida.
export SERVER_PORT=${PORT:-10000}

# Inicia o serviço Python (Flask) com Gunicorn em segundo plano
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app &

# Inicia o serviço principal (Java/Spring Boot) em PRIMEIRO PLANO
# Ele usará a porta definida pela variável $SERVER_PORT
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $SERVER_PORT ---"
java -jar -Dserver.port=${SERVER_PORT} app.jar