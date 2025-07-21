#!/bin/bash

# Inicia o serviço de NLP (Python/Flask) em SEGUNDO PLANO na porta 5000.
# O Java irá se comunicar com ele internamente.
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app &

# Aguarda alguns segundos para o serviço Python subir antes que o Java precise dele.
sleep 5 

# Define a porta do serviço Java usando a variável de ambiente do Render,
# com um fallback para 8080 para desenvolvimento local.
export SERVER_PORT=${PORT:-8080}

# Inicia o serviço principal (Java/Spring Boot) em PRIMEIRO PLANO.
# Como este é o último comando, ele manterá o contêiner rodando e
# o Render irá corretamente direcionar o tráfego externo para esta porta.
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $SERVER_PORT ---"
java -jar -Dserver.port=${SERVER_PORT} app.jar