package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * Componente responsável por carregar e gerenciar a ontologia da aplicação.
 * ESTA VERSÃO É OTIMIZADA PARA PRODUÇÃO: ela carrega um modelo pré-inferido
 * de um arquivo .ttl no classpath, evitando o custo de processamento de
 * arquivos Excel e inferência durante a inicialização.
 */
@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);
    private Model model; // Modelo em memória que será carregado do arquivo
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    // O nome do arquivo pré-calculado que deve estar em src/main/resources/
    private static final String PRECOMPUTED_ONTOLOGY_FILE = "ontology_inferred_final.ttl";

    /**
     * Método de inicialização executado pelo Spring Boot ao iniciar a aplicação.
     * Carrega o modelo de ontologia pré-calculado.
     */
    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            logger.info("--- Carregando modelo pré-inferido de '{}' para a memória...", PRECOMPUTED_ONTOLOGY_FILE);
            
            this.model = ModelFactory.createDefaultModel();
            ClassPathResource resource = new ClassPathResource(PRECOMPUTED_ONTOLOGY_FILE);

            // Tenta carregar o arquivo do classpath
            try (InputStream in = resource.getInputStream()) {
                if (in == null) {
                    throw new IllegalStateException("Arquivo de ontologia '" + PRECOMPUTED_ONTOLOGY_FILE + "' não encontrado no classpath. Verifique se o arquivo está em 'src/main/resources/'.");
                }
                // Carrega o grafo completo diretamente para a memória.
                // O RDFDataMgr é eficiente para esta tarefa.
                RDFDataMgr.read(this.model, in, Lang.TURTLE);
            }

            if (this.model.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo pré-calculado foi carregado, mas está vazio.");
            }
            logger.info("<<< SUCESSO! Ontology inicializada com o modelo pré-calculado. Total de triplas: {} >>>", this.model.size());
        
        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE E IRRECUPERÁVEL NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            throw new RuntimeException("Falha crítica ao carregar a ontologia pré-inferida.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Executa uma consulta SPARQL contra o modelo em memória.
     * Este método não precisa de nenhuma alteração em relação à versão original.
     * @param sparqlQuery A consulta a ser executada.
     * @return Uma lista de mapas representando as linhas de resultado.
     */
    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (this.model == null) {
                logger.error("Tentativa de executar consulta em um modelo nulo.");
                return Collections.emptyList();
            }
            
            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query = QueryFactory.create(sparqlQuery);

            try (QueryExecution qexec = QueryExecutionFactory.create(query, this.model)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();
                
                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new LinkedHashMap<>();
                    for (String varName : resultVars) {
                        RDFNode node = soln.get(varName);
                        String value = "N/A";
                        if (node != null) {
                            if (node.isLiteral()) {
                                value = node.asLiteral().getLexicalForm();
                            } else {
                                value = node.toString();
                            }
                        }
                        rowMap.put(varName, value);
                    }
                    resultsList.add(rowMap);
                }
            }
            logger.info("Consulta retornou {} resultados.", resultsList.size());
            return resultsList;
        } catch (Exception e) {
            logger.error("Erro durante a execução da consulta SPARQL.", e);
            return Collections.emptyList();
        } finally {
            lock.readLock().unlock();
        }
    }

    /**
     * Retorna o modelo carregado. Útil para o endpoint de debug.
     * @return O modelo Jena carregado.
     */
    public Model getInferredModel() {
        return this.model;
    }
}