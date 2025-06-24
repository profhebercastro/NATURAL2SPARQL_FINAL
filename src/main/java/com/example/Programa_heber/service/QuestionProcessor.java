package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.util.StreamUtils;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Pattern;

@Service
public class QuestionProcessor {

    private static final Logger logger = LoggerFactory.getLogger(QuestionProcessor.class);

    // --- CONSTANTES ---
    private static final String PYTHON_SCRIPT_NAME = "pln_processor.py";
    private static final String BASE_ONTOLOGY_URI = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    private static final String[] PYTHON_RESOURCES = {
        PYTHON_SCRIPT_NAME,
        "perguntas_de_interesse.txt",
        "sinonimos_map.txt", // Nome corrigido e alinhado com o Python
        "empresa_nome_map.json",
        "setor_map.json"
    };

    @Autowired
    private Ontology ontology;

    private Path pythonScriptPath;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Inicializa o serviço, extraindo os scripts Python e seus recursos necessários
     * do JAR para um diretório temporário, garantindo que possam ser executados.
     */
    @PostConstruct
    public void initialize() throws IOException {
        logger.info("Iniciando QuestionProcessor (@PostConstruct): Configurando ambiente Python...");
        try {
            Path tempDir = Files.createTempDirectory("pyscripts_temp_");
            tempDir.toFile().deleteOnExit(); // Limpa o diretório quando a JVM encerrar

            for (String fileName : PYTHON_RESOURCES) {
                Resource resource = new ClassPathResource(fileName);
                if (!resource.exists()) {
                    throw new FileNotFoundException("Recurso Python essencial não encontrado no classpath: " + fileName);
                }
                Path destination = tempDir.resolve(fileName);
                try (InputStream inputStream = resource.getInputStream()) {
                    Files.copy(inputStream, destination);
                    logger.info("   Recurso '{}' extraído para {}", fileName, destination);
                }
                if (fileName.equals(PYTHON_SCRIPT_NAME)) {
                    this.pythonScriptPath = destination;
                    // Torna o script executável no ambiente (importante para Linux/macOS)
                    boolean executable = this.pythonScriptPath.toFile().setExecutable(true, false);
                    if (!executable) {
                        logger.warn("   Não foi possível tornar o script Python executável. A execução pode falhar dependendo do SO.");
                    }
                }
            }
            logger.info("QuestionProcessor inicializado com sucesso. Ambiente Python pronto em: {}", tempDir);
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA AO CONFIGURAR AMBIENTE PYTHON. A aplicação não funcionará.", e);
            throw e; // Impede a inicialização da aplicação
        }
    }
    
    /**
     * Ponto de entrada principal para processar uma pergunta do usuário.
     * Orquestra a chamada ao PLN (Python), construção da query, execução e formatação da resposta.
     * @param question A pergunta em linguagem natural.
     * @return Um objeto contendo a resposta detalhada, incluindo a query gerada e o resultado.
     */
    public ProcessamentoDetalhadoResposta processQuestion(String question) {
        logger.info("Serviço QuestionProcessor: Iniciando processamento da pergunta: '{}'", question);
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        
        try {
            // 1. Chamar o script Python para análise de PLN
            Map<String, Object> resultadoPython = executePythonScript(question);
            
            if (resultadoPython.containsKey("erro")) {
                String erroPytnon = (String) resultadoPython.get("erro");
                logger.error("Script Python retornou um erro de PLN: {}", erroPytnon);
                respostaDetalhada.setErro("Falha na análise da pergunta: " + erroPytnon);
                return respostaDetalhada;
            }

            // 2. Extrair informações do resultado do Python
            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            if (templateId == null || placeholders == null) {
                respostaDetalhada.setErro("Não foi possível determinar o tipo da pergunta ou extrair detalhes.");
                return respostaDetalhada;
            }
            logger.info("Análise PLN retornou: Template ID='{}', Placeholders={}", templateId, placeholders);

            // 3. Construir a consulta SPARQL
            String conteudoTemplate = readTemplateContent(templateId);
            String sparqlQueryGerada = buildSparqlQuery(conteudoTemplate, placeholders);
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            logger.info("SPARQL Gerada:\n---\n{}\n---", sparqlQueryGerada);

            // 4. Executar a consulta e formatar o resultado
            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQueryGerada);
            String respostaFormatada = formatarResultados(resultados, templateId);
            respostaDetalhada.setResposta(respostaFormatada);
            logger.info("Resposta final formatada: {}", respostaFormatada);

        } catch (Exception e) {
            logger.error("Erro GENÉRICO e inesperado ao processar a pergunta '{}': {}", question, e.getMessage(), e);
            respostaDetalhada.setErro("Ocorreu um erro interno inesperado no servidor. Consulte os logs para mais detalhes.");
        }
        
        return respostaDetalhada;
    }

    /**
     * Constrói a consulta SPARQL final substituindo os placeholders no template.
     * @param templateContent O conteúdo do arquivo de template.
     * @param placeholders Um mapa com os placeholders (ex: #DATA#) e seus valores.
     * @return A string da consulta SPARQL pronta para execução.
     */
    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String queryAtual = templateContent;
        if (placeholders == null) return queryAtual;

        for (Map.Entry<String, String> entry : placeholders.entrySet()) {
            String phKey = entry.getKey();   // Ex: "#ENTIDADE_NOME#"
            String phValue = entry.getValue(); // Ex: "GERDAU S.A."

            if (phValue != null && !phValue.isEmpty()) {
                String phKeyEscapado = Pattern.quote(phKey);
                String valorSubstituicao;

                switch (phKey) {
                    case "#DATA#":
                        valorSubstituicao = "\"" + phValue + "\"^^xsd:date";
                        break;
                    case "#VALOR_DESEJADO#":
                        // Este placeholder é para um nome de propriedade, não um literal.
                        // O template já tem o prefixo b3:, então substituímos apenas o nome.
                        valorSubstituicao = phValue;
                        break;
                    default: // #ENTIDADE_NOME#, #SETOR#
                        // Trata como um literal string, escapando aspas internas.
                        valorSubstituicao = "\"" + phValue.replace("\"", "\\\"") + "\"";
                        break;
                }
                queryAtual = queryAtual.replaceAll(phKeyEscapado, valorSubstituicao);
            }
        }
        return queryAtual;
    }

    /**
     * Executa o script Python de PLN como um processo externo.
     * @param question A pergunta do usuário.
     * @return Um mapa deserializado do JSON retornado pelo script.
     */
    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        // Assume 'python3' está no PATH do contêiner. O Dockerfile garante isso.
        ProcessBuilder pb = new ProcessBuilder("python3", this.pythonScriptPath.toString(), question);
        logger.info("Executando comando Python: {}", String.join(" ", pb.command()));
        
        Process process = pb.start();
        
        // Captura a saída e os erros de forma robusta
        String stdoutResult = StreamUtils.copyToString(process.getInputStream(), StandardCharsets.UTF_8);
        String stderrResult = StreamUtils.copyToString(process.getErrorStream(), StandardCharsets.UTF_8);
        
        int exitCode = process.waitFor();
        
        if (!stderrResult.isEmpty()) {
            logger.warn("Script Python emitiu mensagens no stderr: {}", stderrResult);
        }
        
        if (exitCode != 0) {
            throw new RuntimeException("Script Python falhou com código de saída " + exitCode + ". Erro: " + stderrResult);
        }
        if (stdoutResult.isEmpty()) {
            throw new RuntimeException("Script Python executou com sucesso, mas não retornou nenhuma saída (JSON esperado).");
        }
        
        logger.debug("Saída JSON bruta do Python: {}", stdoutResult);
        return objectMapper.readValue(stdoutResult, new TypeReference<>() {});
    }

    /**
     * Lê o conteúdo de um arquivo de template do classpath.
     */
    private String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId + ".txt";
        String templateResourcePath = "templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) {
            throw new FileNotFoundException("Arquivo de template SPARQL não encontrado: " + templateResourcePath);
        }
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    /**
     * Formata a lista de resultados da consulta SPARQL em uma string legível para o usuário.
     */
    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) {
            return "Não foram encontrados resultados para a sua pergunta.";
        }
        
        StringJoiner joiner;
        
        // Formato especial para múltiplas colunas (ex: Ticker e Volume)
        if ("Template_4A".equals(templateId)) {
            joiner = new StringJoiner("\n");
            joiner.add("Ticker - Volume Negociado"); // Cabeçalho
            joiner.add("-------------------------");
            for (Map<String, String> row : resultados) {
                String ticker = limparValor(row.getOrDefault("ticker", "?"));
                String volume = limparValor(row.getOrDefault("volume", "?"));
                joiner.add(String.format("%-7s - %s", ticker, volume));
            }
            return joiner.toString();
        }

        // Formato padrão para uma única coluna de resultados (ex: preço, lista de tickers)
        joiner = new StringJoiner(", ");
        if (!resultados.get(0).isEmpty()) {
            // Pega o nome da primeira variável de resultado para ser genérico
            String varName = resultados.get(0).keySet().stream().findFirst().orElse("valor");
            
            for (Map<String, String> row : resultados) {
                String valor = row.getOrDefault(varName, "");
                if (!valor.isEmpty()) {
                    joiner.add(limparValor(valor));
                }
            }
        }
        
        String resultadoFinal = joiner.toString();
        return resultadoFinal.isEmpty() ? "Não foram encontrados resultados para a sua pergunta." : resultadoFinal;
    }

    /**
     * Remove metadados de tipo e URIs da ontologia de um valor de resultado.
     */
    private String limparValor(String item) {
        if (item == null) return "";
        // Remove os sufixos de tipo de dado do XML Schema
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        // Remove o prefixo da ontologia, se houver
        if (limpo.startsWith(BASE_ONTOLOGY_URI)) {
            limpo = limpo.substring(BASE_ONTOLOGY_URI.length());
        }
        return limpo.trim();
    }
}