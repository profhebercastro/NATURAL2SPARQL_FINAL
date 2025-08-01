#!/bin/bash
set -e

echo "--- Iniciando serviço de NLP (Python/Gunicorn) na porta 5000 em segundo plano ---"
# 1. Navega para a pasta /app/nlp onde estão os arquivos Python
# 2. Executa o Gunicorn a partir dali. Agora ele encontrará 'nlp_controller.py'
(cd /app/nlp && exec gunicorn --bind 0.0.0.0:5000 nlp_controller:app) &

# Adiciona uma pausa para garantir que o serviço Python esteja totalmente no ar.
echo "Aguardando o serviço de NLP iniciar completamente..."
sleep 15

echo "--- Iniciando serviço principal (Java/Spring Boot) na porta $PORT em primeiro plano ---"
# O Java agora roda em primeiro plano. Ele encontrará seus recursos DENTRO do app.jar.
exec java -jar /app/app.jar