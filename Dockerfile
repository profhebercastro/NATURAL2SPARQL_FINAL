# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8.5-openjdk-17 AS builder

WORKDIR /app

# Cache de dependências (boa prática)
COPY pom.xml .
RUN mvn dependency:go-offline

# Constrói o projeto
COPY src ./src
RUN mvn clean package -DskipTests


# ESTÁGIO 2: Imagem Final de Produção
FROM openjdk:17-jdk-slim

# Instala Python e pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o JAR do Java construído no estágio anterior
# O wildcard (*) garante que pegue o JAR, não importa a versão.
COPY --from=builder /app/target/*.jar app.jar

# Copia a pasta inteira do serviço de NLP
COPY nlp/ ./nlp

# Instala as dependências Python a partir do requirements.txt que está DENTRO da pasta nlp
RUN pip3 install --no-cache-dir -r nlp/requirements.txt

# Copia o script de inicialização e o torna executável
COPY start.sh .
RUN chmod +x start.sh

# Expõe as duas portas que serão usadas pela aplicação
EXPOSE 8080 5000

# Define o comando que será executado quando o container iniciar
CMD ["./start.sh"]