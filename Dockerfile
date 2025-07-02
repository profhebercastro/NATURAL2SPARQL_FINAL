# Arquivo: Dockerfile

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem oficial do Maven com JDK 17 para compilar o projeto Java.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /build

# 1. Instalação das dependências do sistema e do Python PRIMEIRO.
#    Isso aproveita o cache do Docker. Se os pacotes não mudarem, esta camada não será executada novamente.
#    - 'python3-venv' é a melhor prática para criar ambientes virtuais.
RUN apt-get update && \
    apt-get install -y python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# 2. Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# 3. Cria um ambiente virtual Python e instala as dependências nele.
#    Isso isola as dependências do seu projeto e é mais limpo.
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# 4. Copia o resto do código fonte do projeto.
COPY . .

# 5. Executa o build do Maven.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima para reduzir o tamanho e a superfície de ataque.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# 1. Instalação das dependências mínimas do sistema.
#    'python3-venv' é necessário para que o ambiente virtual funcione.
RUN apt-get update && \
    apt-get install -y python3-venv && \
    rm -rf /var/lib/apt/lists/*

# 2. Copia o ambiente virtual Python com as dependências já instaladas do estágio de build.
COPY --from=build /opt/venv /opt/venv

# 3. Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# 4. Define as variáveis de ambiente.
#    - Adiciona o ambiente virtual ao PATH do sistema.
#    - Otimização de Memória para o plano gratuito do Render.
ENV PATH="/opt/venv/bin:$PATH"
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# 5. Expõe a porta que a aplicação Spring Boot usará.
EXPOSE 8080

# 6. Comando para rodar a aplicação. Render.com injeta a variável de ambiente $PORT.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]