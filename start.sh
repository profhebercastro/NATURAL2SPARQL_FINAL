#!/bin/bash
set -e

echo "--- Iniciando serviço de NLP (Python/Flask) na porta 5000 em segundo plano ---"
# 1. Navega para o diretório onde o script Python e os dicionários estão.
# 2. Executa o Gunicorn a partir dali. O Gunicorn agora encontrará 'nlp_controller.py' facilmente.
(cd /app/src/main/resources && exec gunicorn --bind 0.0.0.0:5000 nlp_controller:app) &

# Aguarda um pouco para o serviço Python iniciar completamente.
echo "Aguardando o serviço de NLP iniciar..."
sleep 10 # Aumentei para 10s para garantir, especialmente em ambientes gratuitos.

echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $PORT ---"
# O Java agora roda em primeiro plano, o que é o padrão para o Render.
exec java -jar -Dserver.port=${PORT} app.jar