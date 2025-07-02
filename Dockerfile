# Arquivo: Dockerfile - Versão 4 (Final e Resiliente)

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que JÁ CONTÉM Maven, JDK 17 e Python 3.
# Isso evita a necessidade de 'apt-get' e torna o build mais rápido e confiável.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# CORREÇÃO: Invoca 'pip' como um módulo do python ('python -m pip') para garantir
# que o executável correto seja encontrado, resolvendo o erro "pip: not found".
# Atualiza o pip para a versão mais recente antes de instalar os pacotes.
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
# Esta ordem (dependências primeiro, depois código) otimiza o cache do Docker.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima que já contém Python 3 por padrão (focal).
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas do estágio de build.
# A imagem base 'maven' instala pacotes pip em /usr/local/lib/python3.8/dist-packages.
# Copiamos para o mesmo local na imagem de destino.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Copia os modelos do spaCy já baixados.
COPY --from=build /usr/local/lib/python3.8/dist-packages/pt_core_news_sm-3.7.0 /usr/local/lib/python3.8/dist-packages/pt_core_news_sm-3.7.0

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará.
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]