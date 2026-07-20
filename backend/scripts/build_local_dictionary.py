import argparse
import csv
import gzip
import hashlib
import re
import sqlite3
from pathlib import Path


CEDICT_PATTERN = re.compile(r'^(\S+) (\S+) \[([^]]+)] /(.*)/$')


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def aliases(exchange: str) -> list[str]:
    return [item.split(':', 1)[1].casefold() for item in exchange.split('/') if ':' in item and item.split(':', 1)[1]]


def build(ecdict_csv: Path, cedict_gzip: Path, output: Path, version: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix('.sqlite3.part')
    partial.unlink(missing_ok=True)
    connection = sqlite3.connect(partial)
    try:
        connection.executescript('''
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE ecdict (word TEXT PRIMARY KEY COLLATE NOCASE, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT);
            CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY COLLATE NOCASE, word TEXT NOT NULL);
            CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        ''')
        with ecdict_csv.open(encoding='utf-8-sig', newline='') as source:
            for row in csv.DictReader(source):
                word = (row.get('word') or '').strip().casefold()
                if not word:
                    continue
                connection.execute('INSERT OR REPLACE INTO ecdict VALUES (?, ?, ?, ?, ?)', (
                    word, row.get('phonetic'), row.get('translation'), row.get('definition'), row.get('pos'),
                ))
                for alias in aliases(row.get('exchange') or ''):
                    connection.execute('INSERT OR IGNORE INTO ecdict_aliases VALUES (?, ?)', (alias, word))
        with gzip.open(cedict_gzip, 'rt', encoding='utf-8') as source:
            for line in source:
                if line.startswith('#'):
                    continue
                match = CEDICT_PATTERN.match(line.strip())
                if match:
                    traditional, simplified, pinyin, definitions = match.groups()
                    connection.execute('INSERT INTO cedict VALUES (?, ?, ?, ?)', (simplified, traditional, pinyin, definitions))
        connection.executescript('CREATE INDEX cedict_simplified ON cedict(simplified); CREATE INDEX cedict_traditional ON cedict(traditional);')
        metadata = {
            'version': version,
            'ecdict_sha256': checksum(ecdict_csv),
            'cc_cedict_sha256': checksum(cedict_gzip),
            'ecdict_license': 'MIT',
            'cc_cedict_license': 'CC BY-SA 3.0',
        }
        connection.executemany('INSERT INTO metadata VALUES (?, ?)', metadata.items())
        connection.commit()
    finally:
        connection.close()
    partial.replace(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ecdict', type=Path, required=True)
    parser.add_argument('--cedict', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    build(args.ecdict, args.cedict, args.output, args.version)
