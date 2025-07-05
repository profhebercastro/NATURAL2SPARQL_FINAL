# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8.5-openjdk-17 AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests


# ESTÁGIO 2: Imagem Final de Produção
FROM openjdk:17-jdk-slim

# Instala o Python e o pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho na imagem final
WORKDIR /app

# --- MUDANÇAS AQUI ---

# 1. Copia o JAR do estágio de build
COPY --from=builder /app/target/*.jar app.jar

# 2. Copia os scripts Python e TODOS os seus arquivos de configuração DIRETAMENTE
#    do seu projeto local para a pasta /app/resources na imagem final.
#    Isso garante que TUDO que o Python precisa estará lá.
COPY src/main/resources/ ./resources/

# 3. Copia os arquivos de configuração do ambiente Python
COPY requirements.txt .
COPY start.sh .

# -------------------------

# Instala as dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Torna o script de inicialização executável
RUN chmod +x start.sh

# Expõe as portas
EXPOSE 8080
EXPOSE 5000

# Comando final para iniciar a aplicação
CMD ["./start.sh"]