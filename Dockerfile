# -----------------------------------------------------------------
# ARQUIVO: Dockerfile (VERSÃO FINAL E CORRIGIDA v2)
# -----------------------------------------------------------------

# Estágio 1: Build da Aplicação Java com Maven
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

WORKDIR /build

# Copia o pom.xml para aproveitar o cache de dependências
COPY pom.xml .

# A linha "COPY .mvn/ .mvn/" foi REMOVIDA daqui pois a pasta não existe no repositório.

# Baixa as dependências do Maven
RUN mvn dependency:go-offline

# Copia o resto do código fonte para o contêiner
COPY src ./src

# Compila e empacota a aplicação
RUN mvn clean package -DskipTests

# ---

# Estágio 2: Criação da Imagem Final de Produção
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# Instala Python e dependências
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Baixa o modelo de linguagem do spaCy
RUN python3 -m spacy download pt_core_news_lg

# Copia o JAR do estágio de build
COPY --from=build /build/target/*.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]