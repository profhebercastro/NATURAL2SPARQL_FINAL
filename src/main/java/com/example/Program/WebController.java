package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

// Use @RestController para APIs que retornam JSON, não @Controller
@RestController
public class WebController {

    private static final Logger logger = LoggerFactory.getLogger(WebController.class);

    // Injeta os serviços necessários que fazem o trabalho pesado
    private final SPARQLProcessor sparqlProcessor;
    private final Ontology ontology;

    @Autowired
    public WebController(SPARQLProcessor sparqlProcessor, Ontology ontology) {
        this.sparqlProcessor = sparqlProcessor;
        this.ontology = ontology;
    }

    /**
     * Endpoint principal da aplicação.
     * Recebe uma pergunta em linguagem natural, gera a consulta SPARQL e a executa.
     * @param perguntaRequest Objeto JSON com o campo "pergunta".
     * @return Uma resposta detalhada contendo a query gerada e o resultado.
     */
    @PostMapping("/processar-pergunta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> processarPergunta(@RequestBody PerguntaRequest perguntaRequest) {
        String pergunta = perguntaRequest.getPergunta();
        logger.info("Recebida requisição para processar a pergunta: '{}'", pergunta);
        
        try {
            // 1. Gera a consulta SPARQL a partir da pergunta
            ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(pergunta);
            
            // Se a query foi gerada com sucesso, executa
            if (resposta.getSparqlQuery() != null && !resposta.getSparqlQuery().isEmpty()) {
                logger.info("Executando a consulta gerada...");
                List<Map<String, String>> resultados = ontology.executeQuery(resposta.getSparqlQuery());
                resposta.setResultado(resultados);
            } else {
                 logger.warn("Nenhuma consulta SPARQL foi gerada para a pergunta.");
            }
            
            return ResponseEntity.ok(resposta);

        } catch (Exception e) {
            logger.error("Erro no processamento da pergunta: {}", pergunta, e);
            ProcessamentoDetalhadoResposta erroResposta = new ProcessamentoDetalhadoResposta();
            erroResposta.setErro("Falha interna ao processar a pergunta.");
            return ResponseEntity.internalServerError().body(erroResposta);
        }
    }

    /**
     * Endpoint de depuração para executar uma consulta SPARQL diretamente.
     * @param request Objeto JSON com o campo "query".
     * @return A lista de resultados da consulta.
     */
    @PostMapping("/execute-query")
    public ResponseEntity<List<Map<String, String>>> executeQuery(@RequestBody ExecuteQueryRequest request) {
        String query = request.getQuery();
        logger.info("Recebida requisição para EXECUTAR a consulta direta:\n{}", query);
        try {
            List<Map<String, String>> resultados = ontology.executeQuery(query);
            return ResponseEntity.ok(resultados);
        } catch (Exception e) {
            logger.error("Erro na execução da consulta direta: {}", query, e);
            return ResponseEntity.internalServerError().build();
        }
    }
}