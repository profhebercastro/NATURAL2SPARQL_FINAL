# Estágio 1: Build do projeto Java usando Maven
FROM maven:3.9-eclipse-temurin-17 AS builder

# Define o diretório de trabalho para o build
WORKDIR /build

# Copia o pom.xml para aproveitar o cache de dependências do Docker
COPY pom.xml .
RUN mvn dependency:go-offline

# Copia todo o código fonte
COPY src ./src

# Compila o projeto e cria o JAR executável. -DskipTests acelera o build.
# O JAR já conterá todos os resources (ontologias, datasets, etc.)
RUN mvn clean install -DskipTests

# Estágio 2: Criação da imagem final e leve para execução
FROM python:3.9-slim

# Define o diretório de trabalho final da aplicação
WORKDIR /app

# Instala o OpenJDK 17, necessário para rodar o JAR
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Copia os arquivos de requisitos do Python e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download pt_core_news_sm

# Copia o JAR compilado do estágio de build para a imagem final
COPY --from=builder /build/target/*.jar app.jar

# Copia o web_app.py para a raiz do app
COPY web_app.py .

# Expõe a porta que o Gunicorn/Flask vai usar
EXPOSE 10000

# Comando final para iniciar AMBAS as aplicações
# 1. Inicia a aplicação Java (Spring Boot) em background (&)
# 2. Inicia o Gunicorn (que serve o web_app.py) em primeiro plano
CMD java -jar app.jar & gunicorn --bind 0.0.0.0:$PORT --workers 2 web_app:app