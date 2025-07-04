#!/bin/bash

# Inicia o serviço Java (sua aplicação Spring Boot) em segundo plano
# O '&' no final faz com que ele rode em background
echo "Iniciando o serviço Java..."
java -jar app.jar &

# Espera um pouco para garantir que o serviço Java comece a inicializar
sleep 10

# Inicia o serviço Python (o servidor Flask) em primeiro plano
# gunicorn é um servidor de produção mais robusto para Flask
# --bind: define o endereço e a porta que o serviço vai escutar
# --workers: número de processos para lidar com requisições
# 'src.main.resources.nlp_controller:app': caminho para o objeto Flask 'app'
echo "Iniciando o serviço Python com Gunicorn..."
gunicorn --bind 0.0.0.0:5000 --workers 2 'src.main.resources.nlp_controller:app'