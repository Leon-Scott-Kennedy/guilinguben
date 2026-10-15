package com.guilinguben.backend.dto;

import jakarta.validation.constraints.NotBlank;

public record ExplainTextRequest(
    @NotBlank String question
) {
}
