package com.example.Programa_heber.model;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * DTO (Data Transfer Object) que encapsula a resposta completa do processamento.
 * Este objeto é serializado para JSON e enviado ao frontend.
 */
@JsonInclude(JsonInclude.Include.NON_NULL) // Opcional, mas recomendado: omite campos nulos da resposta JSON.
public class ProcessamentoDetalhadoResposta {

    private String sparqlQuery;
    private String resposta;
    private String erro;

    // Construtores
    public ProcessamentoDetalhadoResposta() {
        // Construtor padrão necessário para deserialização do Jackson.
    }

    // Getters e Setters
    public String getSparqlQuery() {
        return sparqlQuery;
    }

    public void setSparqlQuery(String sparqlQuery) {
        this.sparqlQuery = sparqlQuery;
    }

    public String getResposta() {
        return resposta;
    }

    public void setResposta(String resposta) {
        this.resposta = resposta;
    }

    public String getErro() {
        return erro;
    }

    public void setErro(String erro) {
        this.erro = erro;
    }

    @Override
    public String toString() {
        // Formata o toString para ser mais legível nos logs, especialmente para a query SPARQL.
        String queryFormatada = (sparqlQuery != null) ? sparqlQuery.replace("\n", " ").replace("\r", " ") : "null";
        return "ProcessamentoDetalhadoResposta{" +
                "sparqlQuery='" + queryFormatada + '\'' +
                ", resposta='" + resposta + '\'' +
                ", erro='" + erro + '\'' +
                '}';
    }
}