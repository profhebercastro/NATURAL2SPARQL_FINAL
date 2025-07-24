package com.example.Program.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class ExecuteQueryRequest {
    
    private String query;

    // Getters e Setters
    
    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }
}package com.example.Program.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class ExecuteQueryRequest {
    
    private String query;
    private String tipoMetrica;

    // Getters e Setters
    
    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }

    public String getTipoMetrica() {
        return tipoMetrica;
    }

    public void setTipoMetrica(String tipoMetrica) {
        this.tipoMetrica = tipoMetrica;
    }
}