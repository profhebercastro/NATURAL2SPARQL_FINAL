# Arquivo: Dockerfile (VERSÃO CORRIGIDA E SIMPLIFICADA)

# Estágio 1: Build com Maven
# Usa uma imagem oficial do Maven com JDK 17 para compilar o projeto Java.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

WORKDIR /build

# Copia todo o código-fonte
# A cópia em múltiplos passos para cache é boa, mas para garantir que tudo funcione,
# vamos copiar tudo de uma vez.
COPY . .

# Comando crucial: Instala as dependências Python e o modelo de linguagem
# ANTES de compilar o Java, para que os scripts estejam disponíveis para serem empacotados.
RUN apt-get update && apt-get install -y python3 python3-pip && \
    pip3 install spacy==3.7.2 && \
    python3 -m spacy download pt_core_news_sm

# Compila o projeto Java, empacotando tudo (incluindo os scripts Python) no JAR.
RUN mvn clean package -DskipTests

# Estágio 2: Execução
# Usa uma imagem mínima com apenas o Java 17 JRE e Python para rodar a aplicação
FROM openjdk:17-jre-slim

# Instala o Python 3, que é necessário para o QuestionProcessor chamar o script de PLN.
RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o JAR do estágio de build para o estágio de execução
COPY --from=build /build/target/*.jar app.jar

# Expõe a porta que o Spring Boot usa por padrão (8080)
EXPOSE 8080

# Comando para rodar a aplicação Spring Boot.
# O Render definirá a variável de ambiente $PORT.
# Passamos essa variável para o Spring Boot para que ele escute na porta correta.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]