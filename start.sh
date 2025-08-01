#!/bin/bash
# Este script inicia os dois serviços de forma robusta e compatível.
# 'set -e' garante que o script saia imediatamente se um comando falhar.
set -e

echo "--- Iniciando serviço principal (Java/Spring Boot) em segundo plano ---"
# O '&' no final é crucial para rodar o Java em background.
java -jar /app/app.jar &

# Adiciona uma pausa mais longa para garantir que o serviço Java esteja totalmente no ar.
# Em ambientes gratuitos, o tempo de inicialização pode variar.
echo "Aguardando o serviço Java iniciar completamente..."
sleep 15

echo "--- Iniciando serviço de NLP (Python/Flask) em primeiro plano ---"
# Usamos 'exec' para que o Python se torne o processo principal, o que é ideal para containers.
# Fornecemos o CAMINHO COMPLETO para o script para eliminar qualquer ambiguidade.
exec python3 /app/src/main/resources/nlp_controller.py