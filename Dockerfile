# Estágio 1: Build do projeto Java usando Maven
# Usamos uma imagem que já tem Maven e Java 17, otimizada para builds
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build

# Copia o pom.xml e baixa as dependências para aproveitar o cache
COPY pom.xml .
RUN mvn dependency:go-offline

# Copia todo o código fonte
COPY src ./src

# Compila o projeto e cria o JAR executável, pulando os testes para acelerar
RUN mvn clean install -DskipTests


# Estágio 2: Criação da Imagem Final para Execução
# Começamos com uma imagem Python leve
FROM python:3.9-slim

WORKDIR /app

# --- CORREÇÃO PRINCIPAL AQUI ---
# Instala o OpenJDK 17 (JRE é suficiente para rodar) E as ferramentas de build (gcc)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Agora, com o gcc instalado, podemos instalar as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download pt_core_news_sm

# Copia os artefatos necessários da aplicação
COPY --from=builder /build/target/*.jar app.jar
COPY web_app.py .

# Expõe a porta que a aplicação vai usar
EXPOSE 10000

# Comando final para iniciar ambas as aplicações
# O JAR do Spring Boot será executado em background
# O Gunicorn servirá a aplicação Flask em primeiro plano
CMD java -jar app.jar & gunicorn --bind 0.0.0.0:$PORT --workers 2 web_app:app