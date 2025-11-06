"""
Testes para validação de qualidade de dados.
"""
import json
import pytest
from pathlib import Path

from src.tools.validate_data import (
    check_missing_fields,
    check_text_too_short,
    check_bad_tokens,
    validate_dataset,
    load_jsonl
)


def test_check_missing_fields():
    """Testa detecção de campos ausentes."""
    # Documento válido
    doc = {"case_number": "1", "content": "conteúdo"}
    assert not check_missing_fields(doc, ["case_number", "content"])
    
    # Campo ausente
    doc_missing = {"case_number": "1"}
    assert check_missing_fields(doc_missing, ["case_number", "content"])
    
    # Campo vazio
    doc_empty = {"case_number": "1", "content": ""}
    assert check_missing_fields(doc_empty, ["case_number", "content"])


def test_check_text_too_short():
    """Testa detecção de texto muito curto."""
    # Texto longo o suficiente
    long_text = "a" * 200
    assert not check_text_too_short(long_text, 200)
    
    # Texto curto
    short_text = "a" * 199
    assert check_text_too_short(short_text, 200)
    
    # Texto com espaços (deve ser stripped)
    text_with_spaces = "   abc   "
    assert check_text_too_short(text_with_spaces, 10)


def test_check_bad_tokens():
    """Testa detecção de tokens HTML/residuais."""
    # Texto limpo
    clean_text = "Este é um texto limpo sem problemas."
    assert not check_bad_tokens(clean_text)
    
    # Texto com ' br ' (espaço antes + word boundary)
    text_br_space = "Linha 1 br Linha 2"
    assert check_bad_tokens(text_br_space)
    
    # Texto com 'br ' (como nos dados reais do STJ)
    text_br_no_before = "DECISÃO br Trata-se de habeas corpus"
    assert check_bad_tokens(text_br_no_before)
    
    # Texto com <br>
    text_br_tag = "Linha 1<br>Linha 2"
    assert check_bad_tokens(text_br_tag)
    
    # Texto com <br/>
    text_br_self_closing = "Linha 1<br/>Linha 2"
    assert check_bad_tokens(text_br_self_closing)
    
    # Texto com &nbsp;
    text_nbsp = "Palavra&nbsp;palavra"
    assert check_bad_tokens(text_nbsp)
    
    # Texto com outras entidades HTML
    text_entity = "Texto com &amp; entidade"
    assert check_bad_tokens(text_entity)
    
    # Texto com tags HTML
    text_html = "Texto com <div>tag</div>"
    assert check_bad_tokens(text_html)


def test_validate_dataset_empty():
    """Testa validação de dataset vazio."""
    docs = []
    report = validate_dataset(docs)
    
    assert report["total"] == 0
    assert report["ok_to_proceed"] is True


def test_validate_dataset_valid():
    """Testa validação de dataset válido (schema case_number/content)."""
    docs = [
        {
            "case_number": "144454780",
            "content": "a" * 300  # Texto longo suficiente
        },
        {
            "case_number": "144381276",
            "content": "b" * 300
        }
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 2
    assert report["missing_fields_pct"] == 0.0
    assert report["too_short_pct"] == 0.0
    assert report["bad_tokens_pct"] == 0.0
    assert report["dupe_ids"] == 0
    assert report["bad_overall_pct"] == 0.0


def test_validate_dataset_missing_fields():
    """Testa validação com campos ausentes."""
    docs = [
        {"case_number": "1", "content": "a" * 300},
        {"case_number": "2"},  # Sem content
        {"content": "c" * 300}  # Sem case_number
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 3
    assert report["missing_fields_pct"] == pytest.approx(66.67, abs=0.1)
    assert report["bad_overall_pct"] > 0


def test_validate_dataset_short_text():
    """Testa validação com textos curtos."""
    docs = [
        {"case_number": "1", "content": "a" * 300},
        {"case_number": "2", "content": "short"},  # Muito curto
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 2
    assert report["too_short_pct"] == 50.0
    assert report["bad_overall_pct"] == 50.0


def test_validate_dataset_bad_tokens():
    """Testa validação com tokens ruins (padrão real STJ)."""
    docs = [
        {"case_number": "1", "content": "a" * 300},
        {"case_number": "2", "content": "DECISÃO br Trata-se de" + "x" * 180},
        {"case_number": "3", "content": "Texto com <br> tag" + "y" * 180},
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 3
    assert report["bad_tokens_pct"] == pytest.approx(66.67, abs=0.1)
    assert report["bad_overall_pct"] > 0


def test_validate_dataset_duplicate_ids():
    """Testa detecção de IDs duplicados."""
    docs = [
        {"case_number": "144454780", "content": "a" * 300},
        {"case_number": "144454780", "content": "b" * 300},  # ID duplicado
        {"case_number": "144381276", "content": "c" * 300},
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 3
    assert report["dupe_ids"] == 1
    assert report["bad_overall_pct"] > 0


def test_validate_dataset_multiple_problems():
    """Testa validação com múltiplos problemas."""
    docs = [
        {"case_number": "1", "content": "a" * 300},  # OK
        {"case_number": "2", "content": "short"},  # Curto
        {"case_number": "3", "content": "DECISÃO br Problema" + "x" * 180},  # Bad token
        {"case_number": "3"},  # ID duplicado + campo ausente
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    assert report["total"] == 4
    assert report["bad_overall_pct"] == 75.0  # 3 docs com problemas


def test_validate_dataset_threshold_gating():
    """Testa gating por threshold."""
    docs = [
        {"case_number": "1", "content": "a" * 300},
        {"case_number": "2", "content": "short"},
    ]
    
    report = validate_dataset(docs, min_chars=200)
    
    # 50% de problemas
    assert report["bad_overall_pct"] == 50.0
    
    # Atualiza com threshold
    max_bad_pct = 10
    report["ok_to_proceed"] = report["bad_overall_pct"] <= max_bad_pct
    
    assert not report["ok_to_proceed"]


def test_load_jsonl(tmp_path):
    """Testa carregamento de arquivo JSONL."""
    # Cria arquivo temporário
    jsonl_file = tmp_path / "test.jsonl"
    
    docs = [
        {"case_number": "1", "content": "Doc 1"},
        {"case_number": "2", "content": "Doc 2"}
    ]
    
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    # Carrega
    loaded = load_jsonl(jsonl_file)
    
    assert len(loaded) == 2
    assert loaded[0]["case_number"] == "1"
    assert loaded[1]["case_number"] == "2"


def test_validate_data_cli_success(tmp_path, monkeypatch):
    """Testa CLI com dataset válido."""
    # Cria arquivo de entrada
    input_file = tmp_path / "input.jsonl"
    docs = [
        {"case_number": "1", "content": "a" * 500},  # Maior que MIN_CHARS default (400)
        {"case_number": "2", "content": "b" * 500}
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    # Caminho do relatório
    report_file = tmp_path / "report.json"
    
    # Simula CLI
    import sys
    from src.tools.validate_data import main
    
    monkeypatch.setattr(
        sys, "argv",
        ["validate_data.py", "--input", str(input_file), "--report", str(report_file), "--min-chars", "200"]
    )
    
    # Executa (deve ter exit 0, mas pytest captura)
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 0
    
    # Verifica relatório
    assert report_file.exists()
    with open(report_file) as f:
        report = json.load(f)
    
    assert report["total"] == 2
    assert report["ok_to_proceed"] is True


def test_validate_data_cli_failure_threshold(tmp_path, monkeypatch):
    """Testa CLI com falha por threshold."""
    # Cria arquivo com muitos problemas
    input_file = tmp_path / "input.jsonl"
    docs = [
        {"case_number": "1", "content": "short"},  # Problema
        {"case_number": "2", "content": "tiny"},   # Problema
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    report_file = tmp_path / "report.json"
    
    # Simula CLI com threshold baixo
    import sys
    from src.tools.validate_data import main
    
    monkeypatch.setattr(
        sys, "argv",
        ["validate_data.py", "--input", str(input_file), "--report", str(report_file), "--max-bad-pct", "10"]
    )
    
    # Executa (deve ter exit 2)
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 2
    
    # Verifica relatório
    with open(report_file) as f:
        report = json.load(f)
    
    assert not report["ok_to_proceed"]


def test_validate_data_cli_missing_file(tmp_path, monkeypatch):
    """Testa CLI com arquivo inexistente."""
    import sys
    from src.tools.validate_data import main
    
    monkeypatch.setattr(
        sys, "argv",
        ["validate_data.py", "--input", "nonexistent.jsonl", "--report", str(tmp_path / "report.json")]
    )
    
    # Executa (deve ter exit 1)
    with pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code == 1
