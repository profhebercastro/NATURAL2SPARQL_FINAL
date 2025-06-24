# Estágio 1: Build do projeto Java usando Maven
# Usa uma imagem oficial que já contém Maven e Java 17
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
# Compila o projeto e cria um JAR executável. A flag -DskipTests acelera o build.
RUN mvn clean install -DskipTests

# Estágio 2: Criação da Imagem Final de Produção
# Começamos com uma imagem Python leve para manter o tamanho final menor
FROM python:3.9-slim
WORKDIR /app

# Instala o JRE (Java Runtime Environment), que é menor que o JDK e suficiente para rodar o JAR
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# O download do spacy pode ser feito aqui ou movido para um script de inicialização se for muito grande
RUN python -m spacy download pt_core_news_sm

# Copia o JAR compilado do estágio de build para a imagem final
COPY --from=builder /build/target/*.jar app.jar

# Copia o web_app.py para a raiz do app
COPY web_app.py .

# Expõe a porta que o Gunicorn/Flask vai usar para o tráfego externo
EXPOSE 10000

# Comando de inicialização
# 1. Inicia a aplicação Java (Spring Boot) em background. O Spring Boot usará a porta 8080 por padrão.
# 2. Inicia o Gunicorn para servir a aplicação Flask, que será o ponto de entrada principal.
CMD java -jar app.jar & gunicorn --bind 0.0.0.0:$PORT --workers 3 --timeout 120 web_app:app