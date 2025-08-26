package com.example.Program.model;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class ProcessamentoDetalhadoResposta {

    private String sparqlQuery;
    private String resposta;
    private String erro;
    private String templateId;
    private String tipoMetrica;
    private String queryType; // NOVO CAMPO ADICIONADO

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

    public String getTemplateId() {
        return templateId;
    }

    public void setTemplateId(String templateId) {
        this.templateId = templateId;
    }

    public String getTipoMetrica() {
        return tipoMetrica;
    }

    public void setTipoMetrica(String tipoMetrica) {
        this.tipoMetrica = tipoMetrica;
    }

    // --- GETTER E SETTER PARA O NOVO CAMPO ---
    public String getQueryType() {
        return queryType;
    }

    public void setQueryType(String queryType) {
        this.queryType = queryType;
    }
}