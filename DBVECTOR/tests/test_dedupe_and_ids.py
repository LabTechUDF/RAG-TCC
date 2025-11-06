"""
Testes para deduplicação e mapeamento de IDs.
"""
import json
import pytest
from pathlib import Path
from src.tools.tratamento_dados import DataProcessor


def test_dedupe_by_id(tmp_path):
    """Testa deduplicação por campo ID."""
    # Cria arquivo de entrada com duplicatas
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Doc 1 - primeira versão"},
        {"id": "2", "text": "Doc 2"},
        {"id": "1", "text": "Doc 1 - versão duplicada"},  # Duplicado
        {"id": "3", "text": "Doc 3"},
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    # Processa com dedupe por ID
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="id",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_read"] == 4
    assert processor.stats["records_written"] == 3
    assert processor.stats["duplicates_removed"] == 1
    
    # Verifica conteúdo de saída
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    assert len(output_docs) == 3
    ids = [doc["id"] for doc in output_docs]
    assert ids == ["1", "2", "3"]  # Mantém primeira ocorrência


def test_dedupe_by_hash(tmp_path):
    """Testa deduplicação por hash de campo complexo."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "hash": {"a": 1, "b": 2}},
        {"id": "2", "hash": {"x": 10}},
        {"id": "3", "hash": {"a": 1, "b": 2}},  # Hash duplicado
        {"id": "4", "hash": {"x": 10}},  # Hash duplicado
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="hash",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_read"] == 4
    assert processor.stats["records_written"] == 2
    assert processor.stats["duplicates_removed"] == 2


def test_no_dedupe(tmp_path):
    """Testa com deduplicação desabilitada."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Doc 1"},
        {"id": "1", "text": "Doc 1 duplicado"},
        {"id": "1", "text": "Doc 1 triplicado"},
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_read"] == 3
    assert processor.stats["records_written"] == 3
    assert processor.stats["duplicates_removed"] == 0


def test_dedupe_missing_field(tmp_path):
    """Testa deduplicação quando alguns docs não têm o campo."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Doc 1"},
        {"text": "Doc sem ID"},  # Sem campo ID
        {"id": "1", "text": "Doc 1 duplicado"},
        {"text": "Outro doc sem ID"},  # Sem campo ID
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="id",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    # Docs sem ID não são deduplicados entre si
    assert processor.stats["records_written"] == 3
    assert processor.stats["duplicates_removed"] == 1


def test_id_mapping_preserved(tmp_path):
    """Testa que mapeamento de IDs é preservado corretamente."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "abc123", "text": "Doc A", "meta": {"source": "STF"}},
        {"id": "def456", "text": "Doc B", "meta": {"source": "STJ"}},
        {"id": "ghi789", "text": "Doc C", "meta": {"source": "TST"}},
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="id",
        quiet=True
    )
    
    processor.process()
    
    # Verifica que IDs e metadados são preservados
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    assert len(output_docs) == 3
    
    # Verifica preservação de IDs
    assert output_docs[0]["id"] == "abc123"
    assert output_docs[1]["id"] == "def456"
    assert output_docs[2]["id"] == "ghi789"
    
    # Verifica preservação de metadados
    assert output_docs[0]["meta"]["source"] == "STF"
    assert output_docs[1]["meta"]["source"] == "STJ"
    assert output_docs[2]["meta"]["source"] == "TST"


def test_complex_id_types(tmp_path):
    """Testa deduplicação com diferentes tipos de ID."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": 123, "text": "Doc com ID numérico"},
        {"id": "123", "text": "Doc com ID string"},  # Mesmo valor, tipo diferente
        {"id": 456, "text": "Doc com ID numérico 2"},
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="id",
        quiet=True
    )
    
    processor.process()
    
    # Ambos 123 são considerados iguais (convertidos para string)
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    assert len(output_docs) == 2
    assert processor.stats["duplicates_removed"] == 1


def test_unicode_ids(tmp_path):
    """Testa que IDs com caracteres unicode funcionam corretamente."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "São_Paulo_123", "text": "Doc SP"},
        {"id": "Brasília_456", "text": "Doc BSB"},
        {"id": "São_Paulo_123", "text": "Doc SP duplicado"},
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="id",
        quiet=True
    )
    
    processor.process()
    
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    assert len(output_docs) == 2
    ids = [doc["id"] for doc in output_docs]
    assert "São_Paulo_123" in ids
    assert "Brasília_456" in ids
