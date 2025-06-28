# Arquivo: Dockerfile

# Estágio 1: Build com Maven
# Usa uma imagem oficial do Maven com JDK 17 para compilar o projeto Java.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

WORKDIR /build
COPY . .

# Instala as dependências Python e o modelo de linguagem ANTES de compilar o Java.
RUN apt-get update && apt-get install -y python3 python3-pip && \
    pip3 install --no-cache-dir spacy==3.7.2 && \
    python3 -m spacy download pt_core_news_sm

# Compila o projeto Java, empacotando tudo (incluindo os scripts) no JAR.
RUN mvn clean package -DskipTests

# Estágio 2: Execução
# Usa uma imagem mínima com apenas o Java 17 JRE e Python para rodar a aplicação.
FROM eclipse-temurin:17-jre-focal

RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar

# Otimização de Memória para o plano gratuito do Render (512MB)
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que o Spring Boot usa
EXPOSE 8080

# Comando para rodar a aplicação, passando a porta do Render para o Spring.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]