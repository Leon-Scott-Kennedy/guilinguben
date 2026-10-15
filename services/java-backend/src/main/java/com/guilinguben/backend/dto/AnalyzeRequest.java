package com.guilinguben.backend.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public record AnalyzeRequest(
    @NotBlank String sessionId,
    @NotBlank String question,
    boolean strictMode,
    @Min(1) @Max(20) int topK
) {
}
