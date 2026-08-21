import argparse
import csv
import gzip
import hashlib
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

CEDICT_PATTERN = re.compile(r'^(\S+) (\S+) \[([^]]+)] /(.*)/$')

ECDICT_DOWNLOAD_URL = 'https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv'
CEDICT_DOWNLOAD_URL = 'https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz'
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / 'dictionary-data'
USER_AGENT = 'family-learning/1.0 (dictionary builder)'


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def aliases(exchange: str) -> list[str]:
    return [item.split(':', 1)[1].casefold() for item in exchange.split('/') if ':' in item and item.split(':', 1)[1]]


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.part')
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=120) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f'empty download from {url}')
    partial.write_bytes(data)
    partial.replace(target)


def ensure_source(path: Path | None, filename: str, url: str, download_flag: bool, cache_dir: Path) -> Path:
    if path is not None:
        return path
    cached = cache_dir / filename
    if cached.is_file():
        return cached
    if not download_flag:
        raise SystemExit(f'--{filename.partition(".")[0]} not provided and {cached} missing; pass --download to fetch sources.')
    print(f'downloading {filename} ...')
    download(url, cached)
    return cached


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
            CREATE TABLE ecdict (
                word TEXT PRIMARY KEY COLLATE NOCASE, phonetic TEXT, translation TEXT,
                definition TEXT, pos TEXT, collins TEXT, oxford TEXT, tag TEXT, bnc TEXT, frq TEXT
            );
            CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY COLLATE NOCASE, word TEXT NOT NULL);
            CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        ''')
        with ecdict_csv.open(encoding='utf-8-sig', newline='') as source:
            for row in csv.DictReader(source):
                word = (row.get('word') or '').strip().casefold()
                if not word:
                    continue
                connection.execute('INSERT OR REPLACE INTO ecdict VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                    word, row.get('phonetic'), row.get('translation'), row.get('definition'), row.get('pos'),
                    row.get('collins'), row.get('oxford'), row.get('tag'), row.get('bnc'), row.get('frq'),
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
    print(f'built {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ecdict', type=Path, help='path to ecdict.csv (downloaded when omitted with --download)')
    parser.add_argument('--cedict', type=Path, help='path to cc-cedict .txt.gz (downloaded when omitted with --download)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--download', action='store_true', help='fetch missing sources from the internet')
    parser.add_argument('--cache-dir', type=Path, default=DEFAULT_CACHE_DIR, help='source cache directory (default: backend/dictionary-data)')
    args = parser.parse_args()
    ecdict = ensure_source(args.ecdict, 'ecdict.csv', ECDICT_DOWNLOAD_URL, args.download, args.cache_dir)
    cedict = ensure_source(args.cedict, 'cedict_1_0_ts_utf-8_mdbg.txt.gz', CEDICT_DOWNLOAD_URL, args.download, args.cache_dir)
    build(ecdict, cedict, args.output, args.version)
