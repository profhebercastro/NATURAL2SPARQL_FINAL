package com.example.Programa_heber.model;

public class ExecuteQueryRequest {
    // Corrigido para "query" para corresponder ao que o JavaScript envia
    private String query;
    private String templateId;

    // Getters e Setters
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