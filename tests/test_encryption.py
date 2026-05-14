from app.utils.encryption import encrypt_api_key, decrypt_api_key


class TestEncryptDecrypt:
    def test_encrypt_decrypt_roundtrip(self):
        original = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(original)
        assert encrypted != original
        assert encrypted != ""
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self):
        assert encrypt_api_key("") == ""

    def test_decrypt_empty_string(self):
        assert decrypt_api_key("") == ""

    def test_encrypt_long_key(self):
        original = "sk-" + "a" * 200
        encrypted = encrypt_api_key(original)
        assert len(encrypted) > 0
        assert decrypt_api_key(encrypted) == original

    def test_encrypt_special_characters(self):
        original = "sk-!@#$%^&*()_+-=~`{}|:<>?,./\\"
        encrypted = encrypt_api_key(original)
        assert decrypt_api_key(encrypted) == original

    def test_encrypt_unicode_key(self):
        original = "sk-测试密钥中文123🚀"
        encrypted = encrypt_api_key(original)
        assert decrypt_api_key(encrypted) == original

    def test_decrypt_invalid_data_returns_empty(self):
        assert decrypt_api_key("not-valid-encrypted-data") == ""

    def test_different_keys_produce_different_ciphertexts(self):
        key1 = "sk-aaaa"
        key2 = "sk-bbbb"
        assert encrypt_api_key(key1) != encrypt_api_key(key2)

    def test_same_key_decrypts_correctly(self):
        original = "sk-consistent-key"
        enc1 = encrypt_api_key(original)
        enc2 = encrypt_api_key(original)
        assert decrypt_api_key(enc1) == original
        assert decrypt_api_key(enc2) == original
