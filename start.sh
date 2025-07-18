#!/bin/bash

# Define a porta do serviço Java
export SERVER_PORT=${PORT:-10000}

# Inicia o serviço principal (Java/Spring Boot) em SEGUNDO PLANO
# Ele ficará escutando na porta fornecida pelo Render (ou 10000 por padrão)
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $SERVER_PORT ---"
java -jar -Dserver.port=${SERVER_PORT} app.jar &

# Aguarda 30 segundos. Este tempo é crucial para dar ao Spring Boot
# tempo suficiente para iniciar completamente ANTES do Gunicorn.
# O plano gratuito do Render pode ser lento, então um tempo maior é mais seguro.
echo "--- Aguardando 30 segundos para o serviço Java iniciar... ---"
sleep 30

# Agora, inicia o serviço Python (Flask) em PRIMEIRO PLANO
# Como este é o último comando, ele manterá o container rodando.
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app