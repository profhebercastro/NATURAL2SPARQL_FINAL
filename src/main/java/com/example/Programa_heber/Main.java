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

// Nota: A anotação @SpringBootApplication já está em WebController,
// então esta classe atua apenas como um @RestController para a API.
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    private final SPARQLProcessor sparqlProcessor;
    private final Ontology ontology;

    @Autowired
    public Main(SPARQLProcessor sparqlProcessor, Ontology ontology) {
        this.sparqlProcessor = sparqlProcessor;
        this.ontology = ontology;
    }

    /**
     * Endpoint para GERAR a consulta SPARQL.
     * Recebe: {"pergunta": "..."}
     * Retorna: {"sparqlQuery": "SELECT...", "templateId": "Template_1A"}
     */
    @PostMapping("/gerar_consulta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String pergunta = request.getPergunta();
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();

        if (pergunta == null || pergunta.trim().isEmpty()) {
            resposta.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(resposta);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            // O SPARQLProcessor agora retorna um objeto de resposta, não apenas a string.
            resposta = sparqlProcessor.generateSparqlQuery(pergunta);

            if (resposta.getErro() != null) {
                return ResponseEntity.internalServerError().body(resposta);
            }
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /gerar_consulta: {}", e.getMessage(), e);
            resposta.setErro("Erro interno ao gerar a consulta: " + e.getMessage());
            return ResponseEntity.internalServerError().body(resposta);
        }
    }

    /**
     * Endpoint para EXECUTAR uma consulta SPARQL.
     * Recebe: {"sparqlQuery": "SELECT...", "templateId": "..."}
     * Retorna: {"resultado": "..."}
     */
    @PostMapping("/executar_query")
    public ResponseEntity<Map<String, Object>> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getSparqlQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("erro", "A consulta SPARQL não pode estar vazia."));
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            List<Map<String, String>> result = ontology.executeQuery(sparqlQuery);
            return ResponseEntity.ok(Map.of("resultado", result)); // Retorna o resultado estruturado
        } catch (Exception e) {
            logger.error("Erro no endpoint /executar_query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("erro", "Erro interno ao executar a consulta."));
        }
    }
}