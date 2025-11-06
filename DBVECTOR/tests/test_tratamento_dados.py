"""
Testes para o módulo tratamento_dados.

Testa varredura recursiva, filtragem de cluster_name == "unknown",
deduplicação, e processamento de arquivos .json e .jsonl.
"""

import json
import pytest
from pathlib import Path
from src.tools.tratamento_dados import DataProcessor, main
import sys
from unittest.mock import patch


class TestDataProcessor:
    """Testes para a classe DataProcessor."""

    def test_merge_jsonl_e_json(self, tmp_path):
        """
        Testa merge de arquivos .json e .jsonl em subpastas.
        Saída deve conter a soma correta de registros válidos.
        """
        # Criar estrutura de diretórios
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        subdir1 = input_dir / "subdir1"
        subdir1.mkdir()

        subdir2 = input_dir / "subdir2"
        subdir2.mkdir()

        # Criar arquivo .json com lista
        json_file1 = subdir1 / "data1.json"
        data1 = [
            {"id": "1", "texto": "documento 1", "cluster_name": "Direito Civil"},
            {"id": "2", "texto": "documento 2", "cluster_name": "Direito Penal"},
        ]
        json_file1.write_text(json.dumps(data1), encoding="utf-8")

        # Criar arquivo .jsonl
        jsonl_file = subdir2 / "data2.jsonl"
        lines = [
            json.dumps({"id": "3", "texto": "documento 3", "cluster_name": "Trabalhista"}),
            json.dumps({"id": "4", "texto": "documento 4", "cluster_name": "Tributário"}),
        ]
        jsonl_file.write_text("\n".join(lines), encoding="utf-8")

        # Criar arquivo .json com objeto único
        json_file2 = subdir2 / "data3.json"
        data3 = {"id": "5", "texto": "documento 5", "cluster_name": "Administrativo"}
        json_file2.write_text(json.dumps(data3), encoding="utf-8")

        # Processar
        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        # Verificações
        assert exit_code == 0
        assert output_file.exists()

        # Ler saída
        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        assert len(output_records) == 5
        assert processor.stats["records_read"] == 5
        assert processor.stats["records_written"] == 5
        assert processor.stats["files_processed"] == 3

        # Verificar IDs
        ids = {r["id"] for r in output_records}
        assert ids == {"1", "2", "3", "4", "5"}

    def test_filtra_unknown(self, tmp_path):
        """
        Testa filtragem de registros com cluster_name == "unknown"
        em várias capitalizações e com espaços.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Criar arquivo com vários casos de "unknown"
        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "texto": "doc 1", "cluster_name": "unknown"},  # lowercase
            {"id": "2", "texto": "doc 2", "cluster_name": "Unknown"},  # capitalize
            {"id": "3", "texto": "doc 3", "cluster_name": " UNKNOWN "},  # uppercase + espaços
            {"id": "4", "texto": "doc 4", "cluster_name": "Válido"},  # válido
            {"id": "5", "texto": "doc 5", "cluster_name": "  unknown  "},  # espaços
            {"id": "6", "texto": "doc 6", "cluster_name": "Outro Válido"},  # válido
            {"id": "7", "texto": "doc 7", "cluster": "unknown"},  # variante cluster
            {"id": "8", "texto": "doc 8", "clusterName": "UNKNOWN"},  # variante clusterName
            {"id": "9", "texto": "doc 9"},  # sem cluster_name - válido
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        # Processar
        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        # Verificações
        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas 3 registros válidos: id 4, 6, 9
        assert len(output_records) == 3
        ids = {r["id"] for r in output_records}
        assert ids == {"4", "6", "9"}

        # Estatísticas
        assert processor.stats["records_read"] == 9
        assert processor.stats["records_written"] == 3
        assert processor.stats["filtered_unknown"] == 6

    def test_dedupe_id(self, tmp_path):
        """
        Testa deduplicação por ID.
        Registros com mesmo ID devem ser descartados (mantém o primeiro).
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "texto": "primeiro", "cluster_name": "A"},
            {"id": "2", "texto": "segundo", "cluster_name": "B"},
            {"id": "1", "texto": "duplicado", "cluster_name": "C"},  # duplicado
            {"id": "3", "texto": "terceiro", "cluster_name": "D"},
            {"id": "2", "texto": "duplicado", "cluster_name": "E"},  # duplicado
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        # Processar com deduplicação por ID
        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="id",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas 3 registros únicos
        assert len(output_records) == 3
        ids = [r["id"] for r in output_records]
        assert ids == ["1", "2", "3"]

        # Verificar que manteve os primeiros
        assert output_records[0]["texto"] == "primeiro"
        assert output_records[1]["texto"] == "segundo"

        # Estatísticas
        assert processor.stats["records_read"] == 5
        assert processor.stats["records_written"] == 3
        assert processor.stats["duplicates_removed"] == 2

    def test_objeto_vs_lista(self, tmp_path):
        """
        Testa processamento de .json com objeto único e com lista.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Arquivo com objeto único
        obj_file = input_dir / "objeto.json"
        obj_data = {"id": "1", "texto": "único", "cluster_name": "Test"}
        obj_file.write_text(json.dumps(obj_data), encoding="utf-8")

        # Arquivo com lista
        list_file = input_dir / "lista.json"
        list_data = [
            {"id": "2", "texto": "item1", "cluster_name": "Test"},
            {"id": "3", "texto": "item2", "cluster_name": "Test"},
        ]
        list_file.write_text(json.dumps(list_data), encoding="utf-8")

        # Processar
        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        assert len(output_records) == 3
        ids = {r["id"] for r in output_records}
        assert ids == {"1", "2", "3"}

    def test_sem_arquivos(self, tmp_path):
        """
        Testa comportamento quando o diretório está vazio.
        Deve retornar exit code 1.
        """
        input_dir = tmp_path / "empty"
        input_dir.mkdir()

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 1
        assert not output_file.exists()

    def test_linhas_invalidas(self, tmp_path):
        """
        Testa comportamento com linhas inválidas em .jsonl.
        Não deve quebrar, deve contabilizar warning e continuar.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        jsonl_file = input_dir / "data.jsonl"
        lines = [
            json.dumps({"id": "1", "texto": "válido", "cluster_name": "Test"}),
            "{ invalid json !!!",  # linha inválida
            json.dumps({"id": "2", "texto": "válido 2", "cluster_name": "Test"}),
            "",  # linha vazia (ignorada)
            json.dumps({"id": "3", "texto": "válido 3", "cluster_name": "Test"}),
        ]
        jsonl_file.write_text("\n".join(lines), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        # Deve processar normalmente
        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas 3 registros válidos
        assert len(output_records) == 3
        assert processor.stats["records_written"] == 3
        assert processor.stats["invalid_records"] == 1

    def test_registros_nao_objeto(self, tmp_path):
        """
        Testa que registros que não são objetos (dict) são descartados.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "texto": "válido", "cluster_name": "Test"},
            "string inválida",  # não é objeto
            123,  # não é objeto
            ["lista", "inválida"],  # não é objeto
            {"id": "2", "texto": "válido 2", "cluster_name": "Test"},
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas 2 registros válidos
        assert len(output_records) == 2
        assert processor.stats["invalid_records"] == 3

    def test_ignore_hidden(self, tmp_path):
        """
        Testa que arquivos e pastas ocultos são ignorados quando --ignore-hidden=True.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Arquivo normal
        normal_file = input_dir / "normal.json"
        normal_file.write_text(json.dumps([{"id": "1", "cluster_name": "Test"}]), encoding="utf-8")

        # Arquivo oculto
        hidden_file = input_dir / ".hidden.json"
        hidden_file.write_text(json.dumps([{"id": "2", "cluster_name": "Test"}]), encoding="utf-8")

        # Pasta oculta com arquivo
        hidden_dir = input_dir / ".hidden_dir"
        hidden_dir.mkdir()
        hidden_dir_file = hidden_dir / "file.json"
        hidden_dir_file.write_text(json.dumps([{"id": "3", "cluster_name": "Test"}]), encoding="utf-8")

        # Processar com ignore_hidden=True
        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            ignore_hidden=True,
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas 1 registro (do arquivo normal)
        assert len(output_records) == 1
        assert output_records[0]["id"] == "1"

    def test_dedupe_hash(self, tmp_path):
        """
        Testa deduplicação por campo hash.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "hash": "abc123", "cluster_name": "A"},
            {"id": "2", "hash": "def456", "cluster_name": "B"},
            {"id": "3", "hash": "abc123", "cluster_name": "C"},  # hash duplicado
            {"id": "4", "hash": "ghi789", "cluster_name": "D"},
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="hash",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        assert len(output_records) == 3
        hashes = [r["hash"] for r in output_records]
        assert hashes == ["abc123", "def456", "ghi789"]
        assert processor.stats["duplicates_removed"] == 1

    def test_dedupe_none(self, tmp_path):
        """
        Testa que com dedupe_by=none, duplicados não são removidos.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "cluster_name": "A"},
            {"id": "1", "cluster_name": "B"},  # ID duplicado
            {"id": "1", "cluster_name": "C"},  # ID duplicado
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Todos os registros mantidos
        assert len(output_records) == 3
        assert processor.stats["duplicates_removed"] == 0

    def test_campo_texto_nao_obrigatorio(self, tmp_path):
        """
        Testa que registros sem campo 'texto' ainda são processados.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "cluster_name": "A"},  # sem campo texto
            {"id": "2", "texto": "com texto", "cluster_name": "B"},
            {"id": "3", "outro_campo": "xyz", "cluster_name": "C"},  # sem texto
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"
        processor = DataProcessor(
            input_dir=input_dir,
            output_file=output_file,
            dedupe_by="none",
            quiet=True,
        )

        exit_code = processor.process()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        assert len(output_records) == 3


class TestCLI:
    """Testes para a interface de linha de comando."""

    def test_cli_basico(self, tmp_path):
        """Testa execução básica via CLI."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        data_file = input_dir / "data.json"
        data = [
            {"id": "1", "texto": "doc 1", "cluster_name": "A"},
            {"id": "2", "texto": "doc 2", "cluster_name": "unknown"},
        ]
        data_file.write_text(json.dumps(data), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"

        # Simular argumentos CLI
        test_args = [
            "tratamento_dados",
            "--input", str(input_dir),
            "--output", str(output_file),
            "--quiet",
        ]

        with patch.object(sys, "argv", test_args):
            exit_code = main()

        assert exit_code == 0
        assert output_file.exists()

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        assert len(output_records) == 1
        assert output_records[0]["id"] == "1"

    def test_cli_diretorio_inexistente(self, tmp_path):
        """Testa CLI com diretório de entrada inexistente."""
        input_dir = tmp_path / "nao_existe"
        output_file = tmp_path / "output.jsonl"

        test_args = [
            "tratamento_dados",
            "--input", str(input_dir),
            "--output", str(output_file),
            "--quiet",
        ]

        with patch.object(sys, "argv", test_args):
            exit_code = main()

        assert exit_code == 1

    def test_cli_extensions(self, tmp_path):
        """Testa CLI com extensões customizadas."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Arquivo .json (deve ser processado)
        json_file = input_dir / "data.json"
        json_file.write_text(json.dumps([{"id": "1", "cluster_name": "A"}]), encoding="utf-8")

        # Arquivo .txt (não será processado com extensões default)
        txt_file = input_dir / "data.txt"
        txt_file.write_text(json.dumps([{"id": "2", "cluster_name": "B"}]), encoding="utf-8")

        output_file = tmp_path / "output.jsonl"

        # Testar apenas com .json
        test_args = [
            "tratamento_dados",
            "--input", str(input_dir),
            "--output", str(output_file),
            "--extensions", ".json",
            "--quiet",
        ]

        with patch.object(sys, "argv", test_args):
            exit_code = main()

        assert exit_code == 0

        with open(output_file, "r", encoding="utf-8") as f:
            output_records = [json.loads(line) for line in f]

        # Apenas o arquivo .json foi processado
        assert len(output_records) == 1
        assert output_records[0]["id"] == "1"
