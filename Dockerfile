# ESTÁGIO 1: Build da Aplicação Java com Maven
# Usamos uma imagem que já tem Maven e JDK 17
FROM maven:3.8.5-openjdk-17 AS builder

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de definição do projeto primeiro para aproveitar o cache do Docker
COPY pom.xml .

# Copia o resto do código fonte do projeto
COPY src ./src

# Executa o build do Maven para gerar o arquivo .jar, pulando os testes para acelerar o build
RUN mvn clean package -DskipTests


# ESTÁGIO 2: Imagem Final de Produção
# Usamos uma imagem base leve que contém apenas o Java Runtime
FROM openjdk:17-jdk-slim

# Instala o Python e o gerenciador de pacotes pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho na imagem final
WORKDIR /app

# Copia os artefatos necessários do estágio de build (o JAR e os recursos)
COPY --from=builder /app/target/*.jar app.jar
COPY --from=builder /app/src/main/resources ./src/main/resources

# Copia o arquivo de dependências Python
COPY requirements.txt .

# Instala as dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Copia o script de inicialização
COPY start.sh .

# Torna o script de inicialização executável
RUN chmod +x start.sh

# Expõe a porta do serviço Java (8080), que o Render usará como porta principal
EXPOSE 8080

# Expõe a porta do serviço Python (5000) para comunicação interna entre os serviços
EXPOSE 5000

# Comando final para iniciar a aplicação usando o script
CMD ["./start.sh"]