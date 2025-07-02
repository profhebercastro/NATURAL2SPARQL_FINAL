# Arquivo: Dockerfile - Versão 7 (Corrigida e Resiliente a Falhas de Rede)

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que contém Maven e JDK 17.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# --- MELHORIA 1: Torna o APT mais resiliente e eficiente ---
# - Adiciona configuração para tentar a conexão 3 vezes em caso de falha.
# - Atualiza a lista de pacotes.
# - Instala python3 e pip SEM instalar pacotes "recomendados" (mais rápido e menor).
# - Limpa o cache do apt no final para reduzir o tamanho da camada.
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-retries && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# Instala as dependências Python.
# Usar --no-cache-dir é uma boa prática para manter a imagem limpa.
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# --- MELHORIA 2: Instala o interpretador Python de forma resiliente no estágio final ---
# A aplicação Java precisa chamar o 'python3' em tempo de execução.
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-retries && \
    apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas e os modelos do spaCy do estágio de build.
# Isso evita ter que baixar tudo de novo na imagem final.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]