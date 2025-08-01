# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8-openjdk-17 AS builder

WORKDIR /app

# Otimiza o cache copiando o pom.xml primeiro
COPY pom.xml .
RUN mvn dependency:go-offline

# Copia todo o código-fonte
COPY src ./src

# Constrói o projeto Java
RUN mvn clean package -DskipTests


# ====================================================================


# ESTÁGIO 2: Imagem Final de Produção
FROM eclipse-temurin:17-jre-focal

# Instala Python e pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copia o JAR compilado do estágio builder
COPY --from=builder /app/target/*.jar app.jar

# --- CORREÇÃO PRINCIPAL ---
# 2. Copia a pasta 'nlp' inteira e seu conteúdo para a imagem final.
COPY nlp/ /app/nlp/
# ---------------------------

# 3. Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia e torna o script de inicialização executável
COPY start.sh .
RUN chmod +x start.sh

# Render usa a porta 10000 para o serviço principal (Java)
# A porta 5000 é para comunicação interna
EXPOSE 10000 5000

# Define o comando que será executado quando o container iniciar
CMD ["./start.sh"]