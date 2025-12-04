"""
Testes para pipelines de I/O (ingest e round-trip).
"""
import json
import pytest
from pathlib import Path
from src.tools.tratamento_dados import DataProcessor
from src.tools.chunking import chunk_documents
from src.schema import Doc, get_dummy_docs
from src import config


def test_ingest_json_list(tmp_path):
    """Testa ingestão de arquivo JSON contendo lista."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.json"
    docs = [
        {"id": "1", "text": "Doc 1"},
        {"id": "2", "text": "Doc 2"},
        {"id": "3", "text": "Doc 3"}
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False)
    
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
    
    # Verifica saída JSONL
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    assert len(output_docs) == 3
    assert output_docs[0]["id"] == "1"


def test_ingest_json_single_object(tmp_path):
    """Testa ingestão de arquivo JSON com objeto único."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "doc.json"
    doc = {"id": "single", "text": "Single document"}
    
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_written"] == 1
    
    with open(output_file, "r", encoding="utf-8") as f:
        output_doc = json.loads(f.readline())
    
    assert output_doc["id"] == "single"


def test_ingest_jsonl(tmp_path):
    """Testa ingestão de arquivo JSONL."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Doc 1"},
        {"id": "2", "text": "Doc 2"},
        {"id": "3", "text": "Doc 3"}
    ]
    
    with open(input_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_written"] == 3


def test_ingest_mixed_json_jsonl(tmp_path):
    """Testa ingestão de múltiplos arquivos JSON e JSONL."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    # Arquivo JSON
    json_file = input_dir / "docs.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump([{"id": "1", "text": "From JSON"}], f)
    
    # Arquivo JSONL
    jsonl_file = input_dir / "docs.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "2", "text": "From JSONL"}) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_written"] == 2


def test_ingest_nested_directories(tmp_path):
    """Testa ingestão recursiva de diretórios aninhados."""
    input_dir = tmp_path / "input"
    
    # Estrutura: input/subdir1/file1.jsonl, input/subdir2/file2.jsonl
    subdir1 = input_dir / "subdir1"
    subdir2 = input_dir / "subdir2"
    subdir1.mkdir(parents=True)
    subdir2.mkdir(parents=True)
    
    file1 = subdir1 / "file1.jsonl"
    with open(file1, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "1", "text": "From subdir1"}) + "\n")
    
    file2 = subdir2 / "file2.jsonl"
    with open(file2, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "2", "text": "From subdir2"}) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    assert exit_code == 0
    assert processor.stats["records_written"] == 2


def test_round_trip_json_to_jsonl(tmp_path):
    """Testa round-trip: JSON → JSONL → leitura."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    # Dados originais
    original_docs = [
        {"id": "1", "text": "Doc 1", "meta": {"key": "value1"}},
        {"id": "2", "text": "Doc 2", "meta": {"key": "value2"}},
    ]
    
    input_file = input_dir / "docs.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(original_docs, f, ensure_ascii=False)
    
    # Processa para JSONL
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    processor.process()
    
    # Lê de volta
    with open(output_file, "r", encoding="utf-8") as f:
        round_trip_docs = [json.loads(line) for line in f]
    
    # Verifica preservação de dados
    assert len(round_trip_docs) == len(original_docs)
    
    for original, round_trip in zip(original_docs, round_trip_docs):
        assert original["id"] == round_trip["id"]
        assert original["text"] == round_trip["text"]
        assert original["meta"] == round_trip["meta"]


def test_unicode_round_trip(tmp_path):
    """Testa round-trip com caracteres Unicode."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    original_docs = [
        {"id": "1", "text": "Açúcar, São Paulo, Brasília"},
        {"id": "2", "text": "Café, João, José"},
        {"id": "3", "text": "日本語 中文 한국어"}  # Caracteres asiáticos
    ]
    
    input_file = input_dir / "docs.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(original_docs, f, ensure_ascii=False)
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    processor.process()
    
    # Lê de volta
    with open(output_file, "r", encoding="utf-8") as f:
        round_trip_docs = [json.loads(line) for line in f]
    
    # Verifica que unicode foi preservado
    for original, round_trip in zip(original_docs, round_trip_docs):
        assert original["text"] == round_trip["text"]


def test_invalid_json_handling(tmp_path):
    """Testa tratamento de JSON inválido."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    # Arquivo com JSON inválido
    input_file = input_dir / "invalid.json"
    with open(input_file, "w", encoding="utf-8") as f:
        f.write("{invalid json content")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    exit_code = processor.process()
    
    # Deve terminar com sucesso mas sem processar o arquivo
    assert exit_code == 0
    assert processor.stats["records_written"] == 0


def test_empty_lines_in_jsonl(tmp_path):
    """Testa que linhas vazias em JSONL são ignoradas."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "1", "text": "Doc 1"}) + "\n")
        f.write("\n")  # Linha vazia
        f.write("   \n")  # Linha com espaços
        f.write(json.dumps({"id": "2", "text": "Doc 2"}) + "\n")
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    processor.process()
    
    assert processor.stats["records_written"] == 2


def test_filter_unknown_cluster(tmp_path):
    """Testa filtro de cluster_name == 'unknown'."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    input_file = input_dir / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Doc 1", "cluster_name": "valid"},
        {"id": "2", "text": "Doc 2", "cluster_name": "unknown"},
        {"id": "3", "text": "Doc 3", "cluster_name": "another"},
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
    
    processor.process()
    
    # Deve filtrar o doc com cluster_name == "unknown"
    assert processor.stats["records_read"] == 3
    assert processor.stats["records_written"] == 2
    assert processor.stats["filtered_unknown"] == 1
    
    # Verifica que doc "unknown" foi removido
    with open(output_file, "r", encoding="utf-8") as f:
        output_docs = [json.loads(line) for line in f]
    
    ids = [doc["id"] for doc in output_docs]
    assert "2" not in ids


def test_complex_nested_data(tmp_path):
    """Testa preservação de estruturas de dados complexas."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    original_doc = {
        "id": "complex",
        "text": "Doc with complex data",
        "meta": {
            "tags": ["tag1", "tag2", "tag3"],
            "nested": {
                "level1": {
                    "level2": {
                        "value": 123
                    }
                }
            },
            "array_of_objects": [
                {"name": "obj1", "value": 1},
                {"name": "obj2", "value": 2}
            ]
        }
    }
    
    input_file = input_dir / "doc.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump([original_doc], f)
    
    output_file = tmp_path / "output.jsonl"
    processor = DataProcessor(
        input_dir=input_dir,
        output_file=output_file,
        dedupe_by="none",
        quiet=True
    )
    
    processor.process()
    
    # Lê de volta
    with open(output_file, "r", encoding="utf-8") as f:
        round_trip_doc = json.loads(f.readline())
    
    # Verifica preservação de estrutura complexa
    assert round_trip_doc["meta"]["tags"] == ["tag1", "tag2", "tag3"]
    assert round_trip_doc["meta"]["nested"]["level1"]["level2"]["value"] == 123
    assert len(round_trip_doc["meta"]["array_of_objects"]) == 2


class TestChunkingInPipeline:
    """Testes de integração do chunking no pipeline completo."""
    
    def test_build_faiss_pipeline_with_chunking(self):
        """Testa que pipeline usa chunking e gera chunks válidos."""
        # Usa documentos dummy do schema
        docs = get_dummy_docs()
        
        # Aplica chunking como no pipeline
        chunk_docs = chunk_documents(docs, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        
        # Validações básicas
        assert len(chunk_docs) > 0, "Deve gerar pelo menos um chunk"
        assert len(chunk_docs) >= len(docs), "Chunks devem ser >= docs originais"
        
        # Valida que todos chunks têm estrutura correta
        for chunk_doc in chunk_docs:
            assert chunk_doc.id is not None
            assert chunk_doc.text is not None
            assert len(chunk_doc.text) > 0
            assert chunk_doc.meta is not None
            assert 'original_id' in chunk_doc.meta
            assert 'chunk_index' in chunk_doc.meta
            assert 'char_start' in chunk_doc.meta
            assert 'char_end' in chunk_doc.meta
            assert chunk_doc.meta['is_chunk'] is True
    
    def test_chunking_preserves_searchability(self):
        """Testa que chunking preserva informações necessárias para busca."""
        docs = get_dummy_docs()
        chunk_docs = chunk_documents(docs, chunk_size=500, overlap=100)
        
        # Todos chunks devem ter texto suficiente para embedding
        for chunk_doc in chunk_docs:
            assert len(chunk_doc.text) >= 10, "Chunk muito pequeno para embedding"
            
        # Verifica que metadados jurídicos foram preservados
        for chunk_doc in chunk_docs:
            # Pelo menos title ou court deve existir
            assert chunk_doc.title is not None or chunk_doc.court is not None
    
    def test_pipeline_chunk_count_validation(self):
        """Valida contagem de documentos vs chunks no pipeline."""
        docs = get_dummy_docs()
        original_count = len(docs)
        
        # Aplica chunking
        chunk_docs = chunk_documents(docs, chunk_size=200, overlap=50)
        chunk_count = len(chunk_docs)
        
        # Com documentos dummy (textos médios), deve gerar mais chunks que docs
        print(f"Original docs: {original_count}, Chunks: {chunk_count}")
        
        # Validação: pelo menos alguns docs devem ter sido divididos
        assert chunk_count > original_count, \
            f"Esperava chunks > docs, mas {chunk_count} <= {original_count}"
    
    def test_chunk_metadata_for_faiss_store(self):
        """Valida que chunks têm estrutura compatível com FAISSStore.index()."""
        docs = get_dummy_docs()
        chunk_docs = chunk_documents(docs, chunk_size=500, overlap=100)
        
        # FAISSStore.index() espera Doc com: id, text, e opcionalmente metadados
        for chunk_doc in chunk_docs:
            # Campos obrigatórios
            assert hasattr(chunk_doc, 'id')
            assert hasattr(chunk_doc, 'text')
            
            # Campos opcionais mas úteis
            assert hasattr(chunk_doc, 'title')
            assert hasattr(chunk_doc, 'court')
            assert hasattr(chunk_doc, 'meta')
            
            # Meta deve ter info de chunking
            if chunk_doc.meta:
                assert 'original_id' in chunk_doc.meta
                assert 'chunk_index' in chunk_doc.meta
    
    def test_chunking_with_custom_sizes(self):
        """Testa chunking com tamanhos customizados."""
        docs = get_dummy_docs()
        
        # Chunks pequenos
        small_chunks = chunk_documents(docs, chunk_size=100, overlap=20)
        
        # Chunks grandes
        large_chunks = chunk_documents(docs, chunk_size=2000, overlap=400)
        
        # Chunks pequenos devem gerar mais fragmentos
        assert len(small_chunks) > len(large_chunks), \
            "Chunks menores devem gerar mais fragmentos"
        
        # Todos devem ter estrutura válida
        for chunk_doc in small_chunks + large_chunks:
            assert chunk_doc.id is not None
            assert len(chunk_doc.text) > 0
    
    def test_original_doc_reconstruction_info(self):
        """Valida que é possível rastrear chunks de volta ao doc original."""
        docs = get_dummy_docs()
        chunk_docs = chunk_documents(docs, chunk_size=300, overlap=50)
        
        # Para cada doc original, deve haver pelo menos um chunk
        for original_doc in docs:
            matching_chunks = [
                c for c in chunk_docs 
                if c.meta.get('original_id') == original_doc.id
            ]
            assert len(matching_chunks) > 0, \
                f"Doc {original_doc.id} não gerou chunks"
            
            # Chunks devem estar ordenados por chunk_index
            indices = [c.meta['chunk_index'] for c in matching_chunks]
            assert indices == sorted(indices), \
                f"Chunks de {original_doc.id} não estão ordenados"
