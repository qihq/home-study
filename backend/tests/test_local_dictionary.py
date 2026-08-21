import sqlite3


def make_dictionary(path):
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT);
        CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY, word TEXT NOT NULL);
        CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        CREATE INDEX cedict_simplified ON cedict(simplified);
        CREATE INDEX cedict_traditional ON cedict(traditional);
        INSERT INTO metadata VALUES ('version', 'fixture-v1');
        INSERT INTO ecdict VALUES ('apple', '''æpl''', 'n. 苹果\\nv. 苹果化\\nadj. 苹果味的\\n苹果树', 'a round fruit\\nthe fruit of an apple tree', 'n:100');
        INSERT INTO ecdict_aliases VALUES ('apples', 'apple');
        INSERT INTO cedict VALUES ('苹果', '蘋果', 'Ping2 guo3', 'Apple (American tech company)');
        INSERT INTO cedict VALUES ('苹果', '蘋果', 'ping2 guo3', 'apple/CL:個|个[ge4]');
    """)
    connection.commit(); connection.close()


def test_ecdict_exact_and_alias_lookup(tmp_path):
    from app.services.local_dictionary import LocalDictionary

    path = tmp_path / 'dictionary.sqlite3'; make_dictionary(path)
    dictionary = LocalDictionary(path)

    exact = dictionary.lookup('Apple', 'en')
    alias = dictionary.lookup('apples', 'en')
    assert exact.result.primary_translation == '苹果'
    assert [(item.part, item.meaning) for item in exact.result.parts_of_speech] == [
        ('n.', '苹果'), ('v.', '苹果化'), ('adj.', '苹果味的'),
    ]
    assert exact.result.alternatives == ['苹果树']
    assert exact.result.usage_note == 'a round fruit\nthe fruit of an apple tree'
    assert exact.result.phonetic == "'æpl'"
    assert exact.source == 'ecdict'
    assert alias.result.source_text == 'apple'
    assert dictionary.fingerprint == 'local:fixture-v1'


def test_cc_cedict_simplified_and_traditional_lookup(tmp_path):
    from app.services.local_dictionary import LocalDictionary

    path = tmp_path / 'dictionary.sqlite3'; make_dictionary(path)
    dictionary = LocalDictionary(path)

    simplified = dictionary.lookup('苹果', 'zh')
    traditional = dictionary.lookup('蘋果', 'zh')
    assert simplified.result.primary_translation == 'apple'
    assert simplified.result.phonetic == 'ping2 guo3'
    assert simplified.result.alternatives == ['CL:個|个[ge4]', 'Apple (American tech company)']
    assert simplified.source == 'cc-cedict'
    assert traditional.result.primary_translation == 'apple'
    assert dictionary.lookup('不存在', 'zh') is None


def test_extended_ecdict_schema_yields_tags_and_pos_pairing(tmp_path):
    from app.services.local_dictionary import LocalDictionary

    path = tmp_path / 'dictionary.sqlite3'
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, definition TEXT, pos TEXT, collins TEXT, oxford TEXT, tag TEXT, bnc TEXT, frq TEXT);
        CREATE TABLE ecdict_aliases (alias TEXT PRIMARY KEY, word TEXT NOT NULL);
        CREATE TABLE cedict (simplified TEXT, traditional TEXT, pinyin TEXT, definitions TEXT);
        INSERT INTO metadata VALUES ('version', 'extended-v1');
        INSERT INTO ecdict VALUES ('apple', '''æpl''', 'n. 苹果\\n苹果树', 'a round fruit', 'n:100/n:50', '3', '1', 'zk cet4', '8906', '6089');
    """)
    connection.commit(); connection.close()

    result = LocalDictionary(path).lookup('apple', 'en').result

    assert result.word_tags == ['中考', '四级', '柯林斯3星', '牛津3000']
    assert [(part.part, part.meaning) for part in result.parts_of_speech] == [
        ('n.', '苹果'), ('n.', '苹果树'),
    ]
    assert result.phonetic_uk == "'æpl'"


def test_missing_dictionary_is_an_available_but_empty_provider(tmp_path):
    from app.services.local_dictionary import LocalDictionary

    dictionary = LocalDictionary(tmp_path / 'missing.sqlite3')
    assert dictionary.available is False
    assert dictionary.lookup('apple', 'en') is None
