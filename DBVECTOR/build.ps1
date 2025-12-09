# Build FAISS Index - PowerShell Script
# Uso: .\build.ps1

Write-Host "=== Build FAISS Index ===" -ForegroundColor Cyan

# Configurar variáveis de ambiente
$env:SEARCH_BACKEND = "faiss"
$env:USE_FAISS_GPU = "false"

Write-Host "`nConfigurações:" -ForegroundColor Yellow
Write-Host "  SEARCH_BACKEND = $env:SEARCH_BACKEND" -ForegroundColor White
Write-Host "  USE_FAISS_GPU = $env:USE_FAISS_GPU" -ForegroundColor White

Write-Host "`nIndexando documentos..." -ForegroundColor Cyan
python -m src.pipelines.build_faiss

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Build concluído com sucesso!" -ForegroundColor Green
    Write-Host "`nPróximo passo:" -ForegroundColor Cyan
    Write-Host "  .\run-api.ps1" -ForegroundColor White
} else {
    Write-Host "`n✗ Erro no build!" -ForegroundColor Red
    Write-Host "Verifique os logs acima" -ForegroundColor Yellow
    exit 1
}
