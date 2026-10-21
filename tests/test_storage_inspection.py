from io import BytesIO

import pytest

from app.integrations.storage.r2 import R2Config, StorageClient


class ObjectStore:
    def __init__(self, content):
        self.objects = {"temporary.pdf": content}

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[Key]), "ETag": '"stable"'}

    def get_object(self, Bucket, Key, Range, IfMatch):
        if Range != "bytes=0-15" or IfMatch != '"stable"':
            raise ValueError("The inspected object must match its HEAD response")
        return {"Body": BytesIO(self.objects[Key][:16])}

    def copy_object(self, Bucket, Key, CopySource, CopySourceIfMatch):
        if CopySourceIfMatch != '"stable"':
            raise ValueError("A conditional copy is required")
        self.objects[Key] = bytes(self.objects[CopySource["Key"]])


@pytest.mark.parametrize(
    "content,expected",
    [
        (b"%PDF-1.7 data", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n" + b"data", "image/png"),
        (b"\xff\xd8\xff" + b"data", "image/jpeg"),
        (b"RIFF1234WEBPdata", "image/webp"),
        (b"<html>unsafe</html>", "application/octet-stream"),
    ],
)
def test_storage_detects_actual_content_instead_of_declared_metadata(content, expected):
    store = ObjectStore(content)
    storage = StorageClient(R2Config("a", "b", "c", "bucket", "https://storage.test"), client=store)
    info = storage.inspect_object("temporary.pdf")
    assert info.content_type == expected
    assert info.size_bytes == len(content)


def test_confirmed_copy_survives_reuse_of_temporary_put_url():
    store = ObjectStore(b"%PDF-1.7 accepted evidence")
    storage = StorageClient(R2Config("a", "b", "c", "bucket", "https://storage.test"), client=store)
    info = storage.inspect_object("temporary.pdf")
    final_key = storage.finalize_upload("temporary.pdf", info.etag)
    store.objects["temporary.pdf"] = b"<html>replacement</html>"
    assert final_key != "temporary.pdf"
    assert storage.inspect_object(final_key).content_type == "application/pdf"
