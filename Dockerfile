# ESTÁGIO 1: Build da Aplicação Java
FROM maven:3.8.5-openjdk-17 AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# ESTÁGIO 2: Imagem Final de Produção
FROM openjdk:17-jdk-slim
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Copia o JAR do Java
COPY --from=builder /app/target/*.jar app.jar

# Copia TODOS os recursos que o Java precisa (que estão na pasta de build do Maven)
COPY --from=builder /app/target/classes/ ./src/main/resources/

# Copia a pasta inteira do serviço de NLP
COPY nlp/ ./nlp/

# Copia os arquivos de configuração do ambiente
COPY requirements.txt .
COPY start.sh .

# Instala as dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Torna o script de inicialização executável
RUN chmod +x start.sh

EXPOSE 8080
EXPOSE 5000

CMD ["./start.sh"]