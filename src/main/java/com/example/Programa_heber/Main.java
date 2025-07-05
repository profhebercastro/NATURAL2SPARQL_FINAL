package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@SpringBootApplication
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

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
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
     * Contém a lógica de extração SIMPLIFICADA para depuração.
     */
    @PostMapping("/executar_query")
    public ResponseEntity<Map<String, String>> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getSparqlQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("erro", "A consulta SPARQL não pode estar vazia."));
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            List<Map<String, String>> resultList = ontology.executeQuery(sparqlQuery);

            String resultadoFinal;

            // ---- LÓGICA DE EXTRAÇÃO SIMPLIFICADA PARA DEBUG ----
            // Esta lógica tenta extrair apenas o primeiro valor da primeira linha,
            // que é o caso comum para perguntas de "Qual o valor...".
            if (resultList == null || resultList.isEmpty()) {
                resultadoFinal = "A consulta foi executada com sucesso, mas não retornou resultados.";
                logger.warn("A execução da consulta não produziu resultados.");
            } else {
                // Pega o primeiro mapa (a primeira linha de resultado)
                Map<String, String> primeiraLinha = resultList.get(0);
                if (primeiraLinha.isEmpty()) {
                    resultadoFinal = "A consulta retornou uma linha, mas sem valores/colunas.";
                    logger.warn("A execução da consulta retornou uma linha vazia.");
                } else {
                    // Pega o primeiro valor da primeira linha, não importa o nome da variável (?ANS, ?ticker, etc)
                    resultadoFinal = primeiraLinha.values().iterator().next();
                    logger.info("Resultado extraído da consulta: {}", resultadoFinal);
                }
            }
            
            return ResponseEntity.ok(Map.of("resultado", resultadoFinal));

        } catch (Exception e) {
            logger.error("Erro no endpoint /executar_query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("erro", "Erro interno ao executar a consulta."));
        }
    }
}