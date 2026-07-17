from pathlib import Path


def test_text_import_parses_candidates_and_preserves_source_location(tmp_path: Path) -> None:
    from app.services.imports import parse_import_file

    source = tmp_path / 'words.txt'
    source.write_text('Apple\nbanana\n', encoding='utf-8')

    parsed = parse_import_file(source, 'text/plain')

    assert parsed.items == [
        {'display_text': 'Apple', 'normalized_text': 'apple', 'source_location': 'line:1'},
        {'display_text': 'banana', 'normalized_text': 'banana', 'source_location': 'line:2'},
    ]


def test_office_import_reports_missing_parser_instead_of_claiming_success(tmp_path: Path) -> None:
    from app.services.imports import ParserUnavailable, parse_import_file

    source = tmp_path / 'words.xlsx'
    source.write_bytes(b'not-an-xlsx')

    try:
        parse_import_file(source, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except ParserUnavailable as error:
        assert error.code == 'PARSER_UNAVAILABLE'
