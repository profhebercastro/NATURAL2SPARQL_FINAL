package com.example.Programa_heber.model;

public class ExecuteQueryRequest {
    // O nome da variável foi corrigido para "query" para corresponder ao JavaScript
    private String query;
    private String templateId;

    // Getters e Setters atualizados
    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }

    public String getTemplateId() {
        return templateId;
    }

    public void setTemplateId(String templateId) {
        this.templateId = templateId;
    }
}