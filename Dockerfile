# Arquivo: Dockerfile

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que JÁ CONTÉM Maven, JDK 17 e Python 3.
# Isso elimina a necessidade de usar 'apt-get' e torna o build mais rápido e confiável.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# Instala as dependências Python usando o pip que já vem na imagem.
# O --no-cache-dir é uma boa prática para manter a camada pequena.
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
# Esta ordem (dependências primeiro, depois código) otimiza o cache do Docker.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima que também já inclui Python 3.
# A imagem 'eclipse-temurin:17-jre-focal' contém o essencial.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# Instala apenas o 'pip' para poder usar as bibliotecas Python.
# Esta é uma operação muito mais leve e confiável do que instalar o python inteiro.
RUN apt-get update && apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas do estágio de build.
# O diretório de pacotes do sistema na imagem focal é /usr/lib/python3/dist-packages
# e os pacotes do usuário/pip em /usr/local/lib/python3.8/dist-packages.
COPY --from=build /usr/local/lib/python3.8/dist-packages /usr/local/lib/python3.8/dist-packages

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará.
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]