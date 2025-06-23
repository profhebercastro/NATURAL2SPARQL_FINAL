# Usa uma imagem oficial do Python como base. É leve, mas precisa de ferramentas adicionais.
FROM python:3.9-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# --- PASSO CRÍTICO DE CORREÇÃO ---
# Instala o 'build-essential' que contém o compilador 'gcc' e outras ferramentas
# necessárias para compilar pacotes Python que têm código em C/C++.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Agora, com as ferramentas instaladas, podemos copiar e instalar os requisitos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download pt_core_news_sm

# --- Cópia dos arquivos da sua aplicação ---
# Copia os arquivos que estão na raiz do seu projeto para a raiz do /app
COPY web_app.py .
COPY ontologiaB3_com_inferencia.ttl .
COPY pom.xml .

# Copia a pasta de código fonte e recursos Java/Python
# Isso irá criar a estrutura /app/src/main/resources/
COPY src ./src

# --- Build do Projeto Java ---
# Instala o Maven
RUN apt-get update && \
    apt-get install -y --no-install-recommends maven && \
    rm -rf /var/lib/apt/lists/*

# Executa o build do Maven dentro do contêiner para criar o JAR
RUN mvn clean install -DskipTests

# Expõe a porta que o Gunicorn vai usar
EXPOSE 10000

# Comando final para iniciar a aplicação
# O JAR estará em /app/target/Programa_heber-0.0.1-SNAPSHOT.jar (ajuste se o nome for diferente)
# O & executa o JAR em background, e o Gunicorn fica em primeiro plano.
CMD java -jar target/Programa_heber-0.0.1-SNAPSHOT.jar & gunicorn --bind 0.0.0.0:$PORT --workers 2 web_app:app