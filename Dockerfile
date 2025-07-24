# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8.5-openjdk-17 AS builder

WORKDIR /app

# Copia TODOS os arquivos do projeto para o estágio de build
# Isso inclui a pasta 'src', 'pom.xml', a pasta 'nlp', etc.
COPY . .

# Cache de dependências Maven
RUN mvn dependency:go-offline

# Constrói o projeto Java
RUN mvn clean package -DskipTests


# ESTÁGIO 2: Imagem Final de Produção
FROM openjdk:17-jdk-slim

# Instala Python e pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o JAR do Java construído no estágio anterior
COPY --from=builder /app/target/*.jar app.jar

# =======================================================
#  !!! CORREÇÃO CRUCIAL APLICADA AQUI !!!
#  Copia a pasta nlp a partir do estágio de BUILD, não do contexto local.
#  Isso garante que estamos usando a versão mais recente do código do Git.
# =======================================================
COPY --from=builder /app/nlp/ ./nlp

# Instala as dependências Python a partir do requirements.txt que está DENTRO da pasta nlp
RUN pip3 install --no-cache-dir -r nlp/requirements.txt

# Copia o script de inicialização e o torna executável
COPY --from=builder /app/start.sh .
RUN chmod +x start.sh

# Expõe as duas portas que serão usadas pela aplicação
EXPOSE 10000 5000 # Render usa 10000 por padrão para o serviço principal

# Define o comando que será executado quando o container iniciar
CMD ["./start.sh"]