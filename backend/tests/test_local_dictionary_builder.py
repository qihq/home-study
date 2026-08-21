import csv
import gzip


def test_builder_creates_queryable_versioned_dictionary(tmp_path):
    from app.services.local_dictionary import LocalDictionary
    from scripts.build_local_dictionary import build

    ecdict = tmp_path / 'ecdict.csv'
    with ecdict.open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=['word', 'phonetic', 'translation', 'definition', 'pos', 'collins', 'oxford', 'tag', 'exchange'])
        writer.writeheader()
        writer.writerow({'word': 'apple', 'phonetic': 'aepl', 'translation': '苹果', 'definition': 'fruit', 'pos': 'n:100', 'collins': '3', 'oxford': '1', 'tag': 'zk cet4', 'exchange': 's:apples'})
    cedict = tmp_path / 'cedict.txt.gz'
    with gzip.open(cedict, 'wt', encoding='utf-8') as output:
        output.write('# fixture\n蘋果 苹果 [ping2 guo3] /apple/fruit/\n')
    target = tmp_path / 'local-dictionary.sqlite3'

    build(ecdict, cedict, target, 'fixture-build-v1')
    dictionary = LocalDictionary(target)

    lookup = dictionary.lookup('apples', 'en')
    assert lookup.result.primary_translation == '苹果'
    assert lookup.result.word_tags == ['中考', '四级', '柯林斯3星', '牛津3000']
    assert lookup.result.phonetic_uk == 'aepl'
    assert dictionary.lookup('蘋果', 'zh').result.primary_translation == 'apple'
    assert dictionary.fingerprint == 'local:fixture-build-v1'
