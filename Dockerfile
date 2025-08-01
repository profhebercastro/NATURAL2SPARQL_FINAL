# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8.5-openjdk-17 AS builder

WORKDIR /app

# 1. Copia o pom.xml e o requirements.txt para cache de dependências
COPY pom.xml .
COPY requirements.txt .

# 2. Baixa as dependências do Maven (isso raramente muda, então fica em cache)
RUN mvn dependency:go-offline

# 3. Copia todo o resto do código-fonte
COPY . .

# 4. Constrói o projeto Java
RUN mvn clean package -DskipTests


# ====================================================================


# ESTÁGIO 2: Imagem Final de Produção
FROM openjdk:17-jdk-slim

# Instala Python e pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copia o requirements.txt do estágio anterior e instala as dependências Python
#    Isso é feito primeiro para otimizar o cache.
COPY --from=builder /app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 2. Copia todos os recursos necessários do estágio builder
#    Copia o JAR compilado
COPY --from=builder /app/target/*.jar app.jar
#    Copia TODA a pasta de recursos, que inclui o nlp_controller.py e a pasta nlp/
COPY --from=builder /app/src/main/resources ./src/main/resources
#    Copia o script de inicialização
COPY --from=builder /app/start.sh .

# 3. Torna o script de inicialização executável
RUN chmod +x start.sh

# Render usa a porta 10000 por padrão para o serviço principal
EXPOSE 10000 5000

# Define o comando que será executado quando o container iniciar
CMD ["./start.sh"]