import base64
import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import struct
import zipfile
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from app.core.config import get_settings


MAGIC = b'FLVOICE1'
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
MAX_FILE_COUNT = 100
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


class VoicePackageError(Exception):
    pass


@dataclass(frozen=True)
class VoicePackagePreview:
    manifest: dict
    audio_files: tuple[str, ...]


@dataclass(frozen=True)
class StagedVoicePackage:
    preview: VoicePackagePreview
    plaintext_path: Path


_STAGED_IMPORTS: dict[str, StagedVoicePackage] = {}


def _derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P).derive(password.encode())


def _zip_bytes(manifest: dict, audio_files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, sort_keys=True, separators=(',', ':')))
        for name, content in audio_files.items():
            archive.writestr(name, content)
    return output.getvalue()


def create_voice_package(manifest: dict, audio_files: dict[str, bytes], password: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    header = {
        'format_version': 1,
        'kdf': {'name': 'scrypt', 'n': SCRYPT_N, 'r': SCRYPT_R, 'p': SCRYPT_P, 'salt': base64.b64encode(salt).decode()},
        'nonce': base64.b64encode(nonce).decode(),
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(',', ':')).encode()
    ciphertext = AESGCM(_derive_key(password, salt)).encrypt(nonce, _zip_bytes(manifest, audio_files), None)
    return MAGIC + struct.pack('>I', len(header_bytes)) + header_bytes + ciphertext


def decrypt_voice_package(package: bytes, password: str) -> bytes:
    try:
        if package[:8] != MAGIC:
            raise VoicePackageError('VOICE_PACKAGE_INVALID')
        header_length = struct.unpack('>I', package[8:12])[0]
        header = json.loads(package[12:12 + header_length])
        kdf = header['kdf']
        if kdf != {
            'name': 'scrypt', 'n': SCRYPT_N, 'r': SCRYPT_R, 'p': SCRYPT_P, 'salt': kdf['salt'],
        }:
            raise VoicePackageError('VOICE_PACKAGE_INVALID')
        salt = base64.b64decode(kdf['salt'], validate=True)
        nonce = base64.b64decode(header['nonce'], validate=True)
        if len(salt) != 16 or len(nonce) != 12:
            raise VoicePackageError('VOICE_PACKAGE_INVALID')
        return AESGCM(_derive_key(password, salt)).decrypt(nonce, package[12 + header_length:], None)
    except VoicePackageError:
        raise
    except (InvalidTag, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise VoicePackageError('VOICE_PACKAGE_PASSWORD_INVALID') from error


def _validate_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.parts[0] == '':
        raise VoicePackageError('VOICE_PACKAGE_INVALID')


def inspect_voice_package(upload, password: str) -> VoicePackagePreview:
    package = upload.read()
    plaintext = decrypt_voice_package(package, password)
    try:
        with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILE_COUNT or sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise VoicePackageError('VOICE_PACKAGE_INVALID')
            for info in infos:
                _validate_member(info.filename)
            manifest = json.loads(archive.read('manifest.json'))
            audio_files = tuple(info.filename for info in infos if info.filename.startswith('audio/'))
            for voice in manifest.get('voice_versions', []):
                filename = f"audio/{voice['id']}.wav"
                if filename not in audio_files:
                    raise VoicePackageError('VOICE_PACKAGE_INVALID')
                if hashlib.sha256(archive.read(filename)).hexdigest() != voice['reference_sha256']:
                    raise VoicePackageError('VOICE_PACKAGE_INVALID')
            return VoicePackagePreview(manifest=manifest, audio_files=audio_files)
    except VoicePackageError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise VoicePackageError('VOICE_PACKAGE_INVALID') from error


def stage_voice_package_import(upload, password: str) -> tuple[str, VoicePackagePreview]:
    package = upload.read()
    preview = inspect_voice_package(io.BytesIO(package), password)
    plaintext = decrypt_voice_package(package, password)
    import_id = uuid4().hex
    plaintext_path = get_settings().data_dir / 'imports' / 'voice' / f'{import_id}.part'
    plaintext_path.parent.mkdir(parents=True, exist_ok=True)
    plaintext_path.write_bytes(plaintext)
    _STAGED_IMPORTS[import_id] = StagedVoicePackage(preview=preview, plaintext_path=plaintext_path)
    return import_id, preview


def pop_staged_voice_package(import_id: str) -> StagedVoicePackage:
    try:
        return _STAGED_IMPORTS.pop(import_id)
    except KeyError as error:
        raise VoicePackageError('VOICE_PACKAGE_INVALID') from error
