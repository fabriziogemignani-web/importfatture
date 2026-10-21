"""Repro: ZIP whose central directory declares a small file_size but member decompresses to 50MB; and encrypted flag. Shows exceptions escaping extract_xml_files."""
import io
import struct
import sys
import zipfile
import tracemalloc

sys.path.insert(0, "/app/backend")
from fattura_parser import extract_xml_files  # noqa: E402

b = io.BytesIO()
with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("big.xml", b" " * (50 * 1024 * 1024))
data = bytearray(b.getvalue())
for sig, off in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
    i = data.find(sig)
    struct.pack_into("<I", data, i + off, 1000)
tracemalloc.start()
try:
    print(list(extract_xml_files("lie.zip", bytes(data))))
except Exception as e:
    print("lying size ->", type(e).__name__, e)
print("peak MB", tracemalloc.get_traced_memory()[1] / 1e6)

b = io.BytesIO()
with zipfile.ZipFile(b, "w", zipfile.ZIP_STORED) as z:
    z.writestr("e.xml", b"<x/>")
data = bytearray(b.getvalue())
data[data.find(b"PK\x03\x04") + 6] |= 1
data[data.find(b"PK\x01\x02") + 8] |= 1
try:
    print(list(extract_xml_files("enc.zip", bytes(data))))
except Exception as e:
    print("encrypted ->", type(e).__name__, e)
