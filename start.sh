#!/bin/bash

# Inicia o serviço Python (Flask) em segundo plano na porta 5000
echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 ---"
gunicorn --bind 0.0.0.0:5000 --workers 2 nlp.nlp_controller:app &

# Aguarda 5 segundos para o serviço Python estar pronto
sleep 5

# Inicia o serviço Java em PRIMEIRO PLANO, usando a porta fornecida pelo Render
# A variável de ambiente $PORT é injetada automaticamente pelo Render.
# Por padrão, no Spring Boot, a propriedade server.port tem precedência.
echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $PORT ---"
java -jar -Dserver.port=${PORT} app.jar