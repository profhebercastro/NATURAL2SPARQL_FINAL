#!/bin/bash

# Inicia o serviço de NLP (Python/Flask) em SEGUNDO PLANO na porta 5000.
# O Java irá se comunicar com ele internamente usando localhost:5000.
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app &

# Aguarda um pouco. 
# o serviço Python esteja totalmente funcional antes do Java tentar usá-lo.
sleep 5 

# Inicia o serviço principal (Java/Spring Boot) em PRIMEIRO PLANO.
# Este é o comando mais importante. Ele usa a variável $PORT fornecida pelo Render.
# O Render VAI direcionar o tráfego externo para esta porta.
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $PORT ---"
java -jar -Dserver.port=${PORT} app.jar