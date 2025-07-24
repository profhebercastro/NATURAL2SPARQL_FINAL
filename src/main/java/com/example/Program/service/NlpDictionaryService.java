package com.example.Program.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import java.io.IOException;
import java.io.InputStream;
import java.util.Collections;
import java.util.Map;
import java.util.Set;

@Service
public class NlpDictionaryService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Map<String, String> empresaMap;

    @PostConstruct
    public void init() throws IOException {
        try (InputStream in = new ClassPathResource("nlp/Named_entity_dictionary.json").getInputStream()) {
            this.empresaMap = objectMapper.readValue(in, new TypeReference<Map<String, String>>() {});
        }
    }

    public Set<String> getEmpresaKeys() {
        return empresaMap != null ? empresaMap.keySet() : Collections.emptySet();
    }
}