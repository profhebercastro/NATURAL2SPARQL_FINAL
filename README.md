Natural2SPARQL_2025

Natural2SPARQL é um sistema que traduz perguntas em linguagem natural (português) para consultas SPARQL. Ele utiliza uma aplicação backend em Java/Spring Boot que orquestra o processo, chamando um script Python para análise de linguagem natural e consultando uma base de conhecimento RDF com Apache Jena para fornecer respostas aos usuários através de uma interface web.
Funcionalidades Principais

    Tradução de Linguagem Natural para SPARQL: Converte perguntas como "Qual o preço de fechamento da Vale em 05/05/2023?" em consultas SPARQL formais e executáveis.

    Processamento de Linguagem Natural (PLN): Utiliza um script Python com uma abordagem baseada em regras, similaridade de strings (difflib) e dicionários para identificar a intenção do usuário, extrair entidades (empresas, datas, etc.) e normalizá-las.

    Construção Automática da Base de Conhecimento: Utiliza uma ontologia (RDF/TTL) que é automaticamente populada e cacheada na primeira inicialização do sistema, lendo os dados de planilhas Excel (.xlsx) da B3 (informações de empresas, setores, dados históricos de pregões).

    Consultas Baseadas em Templates: Emprega um sistema de templates SPARQL que são preenchidos dinamicamente com as entidades extraídas pela camada de PLN.

    Interface Web Responsiva: Fornece uma interface de usuário single-page (HTML/JS/CSS) servida diretamente pelo backend Java, permitindo a interação em duas etapas: geração da consulta e execução.

    Deploy em Nuvem: O projeto está configurado para deploy na plataforma Render usando Docker.

Tecnologias Utilizadas

    Backend & Orquestração:

        Java 17

        Spring Boot 3

        Apache Jena (para manipulação da ontologia e execução de SPARQL)

        Apache POI (para leitura de arquivos Excel)

    Processamento de Linguagem Natural:

        Python 3.9

        Bibliotecas padrão do Python (difflib, re, json)

    Frontend:

        HTML5, CSS3, JavaScript (Vanilla)

    Base de Dados:

        RDF/TTL (para a base de conhecimento)

        Arquivos Excel (.xlsx) como fonte primária dos dados.

    DevOps:

        Docker (com build multi-stage)

        Maven (para gerenciamento de dependências e build do projeto Java)

Arquitetura e Fluxo de Dados

O sistema opera com um fluxo de requisição claro e bem definido:

    Interface do Usuário (Frontend): O usuário digita uma pergunta no index2.html e clica em "GERAR CONSULTA".

    Controlador REST (Java/Spring Boot): O frontend envia a pergunta para o endpoint /gerar_consulta no backend Java.

    Serviço Orquestrador (Java QuestionProcessor):

        Recebe a pergunta e invoca o script pln_processor.py, passando a pergunta como argumento.

    Processador de PLN (Script Python):

        Analisa a pergunta usando difflib para encontrar o template mais similar em perguntas_de_interesse.txt.

        Extrai e normaliza entidades (empresas, datas, etc.) usando regex e os mapas em empresa_nome_map.json e setor_map.json.

        Retorna um objeto JSON contendo o ID do template e as entidades extraídas para o serviço Java.

    Construtor de Consultas (Java):

        O QuestionProcessor recebe o JSON do Python.

        Lê o arquivo de template SPARQL correspondente (ex: Template_1A.txt).

        Preenche o template com as entidades, gerando a consulta SPARQL final.

        A consulta é enviada de volta para o frontend para exibição.

    Execução da Consulta (Frontend e Backend):

        O usuário clica em "Executar" no frontend.

        A consulta SPARQL e o ID do template são enviados para o endpoint /executar_query.

        O QuestionProcessor passa a consulta para o componente Ontology.

    Motor de Consulta (Java - Ontology com Apache Jena):

        Executa a consulta SPARQL contra o modelo RDF em memória (carregado de ontologiaB3_com_inferencia.ttl).

        Formata o resultado em um formato amigável e retorna para o frontend.

Configuração e Instalação
Pré-requisitos

    Java JDK 17 ou superior

    Apache Maven 3.6+ (para construir o projeto Java)

    Python 3.9 ou superior

    pip (gerenciador de pacotes Python)

    Docker (para rodar em container ou para deploy)

Passos de Instalação Local

    Clone o repositório:
    Generated bash

          
    git clone https://github.com/hebercastro79/Natural2SPARQL_2025.git
    cd Natural2SPARQL_2025

        

    IGNORE_WHEN_COPYING_START

Use code with caution. Bash
IGNORE_WHEN_COPYING_END

Instale as dependências Python:
Generated bash

      
pip install -r requirements.txt

    

IGNORE_WHEN_COPYING_START
Use code with caution. Bash
IGNORE_WHEN_COPYING_END

Nota: requirements.txt pode listar spacy, mas a implementação atual usa apenas bibliotecas padrão do Python, então a instalação é rápida.

Construa e execute a aplicação Java:
Generated bash

      
# Usando o Maven Wrapper (recomendado)
./mvnw spring-boot:run

# Ou, para criar o JAR e executá-lo manualmente:
# 1. Construa o JAR
./mvnw clean package
# 2. Execute o JAR
java -jar target/natural2sparql-0.0.1-SNAPSHOT.jar

    

IGNORE_WHEN_COPYING_START

    Use code with caution. Bash
    IGNORE_WHEN_COPYING_END

    A aplicação estará acessível em http://localhost:8080.

Importante: Na primeira vez que a aplicação é executada, ela irá ler todos os arquivos .xlsx das pastas resources/Datasets e resources/Templates para construir o arquivo de cache da ontologia (target/classes/ontologiaB3_com_inferencia.ttl). Este processo pode levar alguns segundos. Nas inicializações seguintes, o sistema carregará este arquivo de cache diretamente, tornando o startup quase instantâneo.
Executando com Docker

O Dockerfile foi projetado para construir e rodar a aplicação de forma autocontida.

    Construa a imagem Docker:
    Generated bash

          
    docker build -t natural2sparql .

        

    IGNORE_WHEN_COPYING_START

Use code with caution. Bash
IGNORE_WHEN_COPYING_END

Execute o container Docker:
A aplicação é configurada para usar uma porta fornecida pela variável de ambiente PORT.
Generated bash

      
docker run -e PORT=8080 -p 8080:8080 -it natural2sparql

    

IGNORE_WHEN_COPYING_START

    Use code with caution. Bash
    IGNORE_WHEN_COPYING_END

    A aplicação estará acessível em http://localhost:8080.

Como Usar

    Acesse a interface web no link de deploy ou localmente:

        Deploy Público: https://natural2sparql-2025.onrender.com

        Local: http://localhost:8080

    Digite sua pergunta no campo de texto. Exemplos de perguntas suportadas:

        Qual foi o preço de fechamento da ação da CSN em 08/05/2023?

        Qual foi o preço de abertura da CBAV3 em 08/05/2023?

        Qual o código de negociação da ação da Gerdau?

        Quais são as ações do setor eletrico?

        Qual foi o volume negociado nas ações do setor bancário em 05/05/2023?

    Clique em "GERAR CONSULTA". A consulta SPARQL correspondente aparecerá.

    Clique em "Executar". O resultado final será exibido.

Manutenção e Atualização de Dados

O sistema foi projetado para ser facilmente atualizável:

    Atualize os Dados: Substitua ou adicione novos arquivos de dados .xlsx nas pastas:

        src/main/resources/Datasets/ (para dados de pregões)

        src/main/resources/Templates/ (para o arquivo Informacoes_Empresas.xlsx)

    Limpe o Cache: Exclua o arquivo de cache da ontologia gerado anteriormente, que se encontra em:

        target/classes/ontologiaB3_com_inferencia.ttl
        (A forma mais fácil de garantir a limpeza é executar mvn clean).

    Reconstrua e Reinicie: Recompile e reinicie a aplicação.
    Generated bash

          
    # Parar a aplicação se estiver rodando
    ./mvnw clean package
    java -jar target/natural2sparql-0.0.1-SNAPSHOT.jar

        

    IGNORE_WHEN_COPYING_START

    Use code with caution. Bash
    IGNORE_WHEN_COPYING_END

Ao reiniciar, a aplicação detectará a ausência do arquivo de cache e irá gerá-lo novamente usando os novos dados das planilhas.