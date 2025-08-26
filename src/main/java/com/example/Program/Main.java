package com.example.Program;

import com.example.Program.model.ExecuteQueryRequest;
import com.example.Program.model.PerguntaRequest;
import com.example.Program.model.ProcessamentoDetalhadoResposta;
import com.example.Program.ontology.Ontology;
import com.example.Program.service.ResultFormatterService; // Assumindo que você tem um serviço de formatação
import com.example.Program.service.SPARQLProcessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.jena.rdf.model.Model;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.StringWriter;
import java.util.List;
import java.util.Map;

@SpringBootApplication
@RestController
@RequestMapping("/api")
public class Main {
    
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    @Autowired private SPARQLProcessor sparqlProcessor;
    @Autowired private Ontology ontology;
    @Autowired private ObjectMapper objectMapper;
    @Autowired private ResultFormatterService resultFormatter; // Injetando o formatador

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
    @PostMapping("/processar")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String pergunta = request.getPergunta();
        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(pergunta);
        if (resposta.getErro() != null) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(resposta);
        }
        return ResponseEntity.ok(resposta);
    }

    @PostMapping("/executar")
    public ResponseEntity<?> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getQuery();
        String queryType = request.getQueryType();
        
        logger.info("Executando query. Tipo: {}.", queryType);
        
        try {
            if ("ASK".equalsIgnoreCase(queryType)) {
                boolean result = ontology.executeAskQuery(sparqlQuery);
                // Retorna um objeto JSON simples para o resultado booleano
                return ResponseEntity.ok(Map.of("result", result));
            } else {
                // Lógica de execução e formatação para SELECT
                List<Map<String, String>> bindings = ontology.executeSelectQuery(sparqlQuery);
                logger.info("Consulta SELECT retornou {} resultados.", bindings.size());
                String resultadoJson = resultFormatter.formatSelectResults(bindings, request.getTipoMetrica());
                return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(resultadoJson);
            }
        } catch (Exception e) {
            logger.error("Erro no endpoint /executar: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Erro interno ao executar a consulta: " + e.getMessage()));
        }
    }

    @GetMapping("/debug/get-inferred-ontology")
    public ResponseEntity<String> getInferredOntology() {
        // ... (seu método de debug permanece o mesmo) ...
    }
}