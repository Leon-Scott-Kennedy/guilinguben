package com.guilinguben.backend.dto;

import jakarta.validation.constraints.NotBlank;

public record ExplainTextResponse(
    @NotBlank String answer
) {
}
