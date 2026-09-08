from resource_retriever.hashing import compute_content_hash


def test_same_bytes_produce_same_hash():
    data = b"quadratic worksheet content"

    hash_a = compute_content_hash(data)
    hash_b = compute_content_hash(data)

    assert hash_a == hash_b


def test_different_bytes_produce_different_hash():
    hash_a = compute_content_hash(b"content one")
    hash_b = compute_content_hash(b"content two")

    assert hash_a != hash_b


def test_hash_is_a_sha256_hex_digest():
    result = compute_content_hash(b"abc")

    assert len(result) == 64
    assert all(char in "0123456789abcdef" for char in result)
