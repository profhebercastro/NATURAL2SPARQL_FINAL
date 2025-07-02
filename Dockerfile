# Arquivo: Dockerfile - Versão 13 (Baseada na sua excelente alternativa)

# --- ESTÁGIO 1: BUILD DA APLICAÇÃO JAVA COM MAVEN ---
FROM maven:3.9.6-eclipse-temurin-17 AS builder

WORKDIR /build
COPY pom.xml .
# Otimização: baixa as dependências antes para cachear esta camada
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn clean package -DskipTests


# --- ESTÁGIO 2: IMAGEM FINAL DE EXECUÇÃO ---
# Começa com uma imagem Python leve e oficial
FROM python:3.9-slim

WORKDIR /app

# Instala o Java Runtime Environment (JRE) e as ferramentas de build para o Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos
COPY requirements.txt .

# Instala as dependências Python (modelo incluído) de forma robusta
RUN pip install --no-cache-dir -r requirements.txt

# Copia o JAR executável criado no estágio anterior
COPY --from=builder /build/target/*.jar app.jar

# Expõe a porta que o Render vai usar. O valor real virá da variável $PORT
EXPOSE 10000

# Comando para iniciar a aplicação Java, compatível com a injeção de porta do Render
# Usamos a forma "exec" para que o Java seja o processo principal (PID 1)
CMD ["java", "-Dserver.port=${PORT}", "-jar", "/app/app.jar"]