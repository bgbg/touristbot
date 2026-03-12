"""
Unit tests for WhatsAppConfig multi-number routing config.
"""
import pytest
from whatsapp.config import WhatsAppConfig, PhoneNumberConfig


DEFAULT_AREA = "עמק חפר"
DEFAULT_SITE = "אגמון חפר"


class TestParsePhoneNumberMap:
    def test_empty_string_returns_empty_dict(self):
        result = WhatsAppConfig._parse_phone_number_map("", DEFAULT_AREA, DEFAULT_SITE)
        assert result == {}

    def test_whitespace_only_returns_empty_dict(self):
        result = WhatsAppConfig._parse_phone_number_map("   ", DEFAULT_AREA, DEFAULT_SITE)
        assert result == {}

    def test_single_valid_entry(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1", DEFAULT_AREA, DEFAULT_SITE
        )
        assert len(result) == 1
        pnc = result["111"]
        assert pnc.phone_number_id == "111"
        assert pnc.access_token == "token1"
        assert pnc.area == "area1"
        assert pnc.site == "site1"

    def test_two_valid_entries(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1,222:token2:area2:site2", DEFAULT_AREA, DEFAULT_SITE
        )
        assert len(result) == 2
        assert result["111"].area == "area1"
        assert result["222"].area == "area2"

    def test_entry_with_empty_area_falls_back_to_default(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1::site1", DEFAULT_AREA, DEFAULT_SITE
        )
        assert result["111"].area == DEFAULT_AREA
        assert result["111"].site == "site1"

    def test_entry_with_empty_site_falls_back_to_default(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:", DEFAULT_AREA, DEFAULT_SITE
        )
        assert result["111"].area == "area1"
        assert result["111"].site == DEFAULT_SITE

    def test_malformed_entry_wrong_field_count_raises(self):
        with pytest.raises(ValueError, match="expected 'phone_number_id:access_token:area:site"):
            WhatsAppConfig._parse_phone_number_map("111:token1:area1", DEFAULT_AREA, DEFAULT_SITE)

    def test_entry_with_app_secret(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1:mysecret", DEFAULT_AREA, DEFAULT_SITE
        )
        assert result["111"].app_secret == "mysecret"

    def test_entry_without_app_secret_is_none(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1", DEFAULT_AREA, DEFAULT_SITE
        )
        assert result["111"].app_secret is None

    def test_malformed_entry_too_many_fields_raises(self):
        with pytest.raises(ValueError):
            WhatsAppConfig._parse_phone_number_map("111:token1:area1:site1:secret:extra", DEFAULT_AREA, DEFAULT_SITE)

    def test_empty_phone_number_id_raises(self):
        with pytest.raises(ValueError, match="phone_number_id and access_token must not be empty"):
            WhatsAppConfig._parse_phone_number_map(":token1:area1:site1", DEFAULT_AREA, DEFAULT_SITE)

    def test_empty_access_token_raises(self):
        with pytest.raises(ValueError, match="phone_number_id and access_token must not be empty"):
            WhatsAppConfig._parse_phone_number_map("111::area1:site1", DEFAULT_AREA, DEFAULT_SITE)

    def test_trailing_comma_ignored(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1,", DEFAULT_AREA, DEFAULT_SITE
        )
        assert len(result) == 1

    def test_result_values_are_phone_number_config_instances(self):
        result = WhatsAppConfig._parse_phone_number_map(
            "111:token1:area1:site1", DEFAULT_AREA, DEFAULT_SITE
        )
        assert isinstance(result["111"], PhoneNumberConfig)


class TestPhoneNumberMapSeeding:
    """Test that primary single-number vars are seeded into phone_number_map."""

    def test_primary_number_seeded_when_no_map(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "primary_id")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "primary_token")
        monkeypatch.delenv("PHONE_NUMBER_MAP", raising=False)
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "tok")
        monkeypatch.setenv("BACKEND_API_KEY", "key")
        monkeypatch.setenv("GCS_BUCKET", "bucket")

        config = WhatsAppConfig.from_env()
        assert "primary_id" in config.phone_number_map
        assert config.phone_number_map["primary_id"].access_token == "primary_token"

    def test_primary_not_duplicated_when_in_map(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "primary_id")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "primary_token")
        monkeypatch.setenv("PHONE_NUMBER_MAP", "primary_id:map_token:area1:site1")
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "tok")
        monkeypatch.setenv("BACKEND_API_KEY", "key")
        monkeypatch.setenv("GCS_BUCKET", "bucket")

        config = WhatsAppConfig.from_env()
        # Map entry takes precedence; primary not duplicated
        assert len([k for k in config.phone_number_map if k == "primary_id"]) == 1
        assert config.phone_number_map["primary_id"].access_token == "map_token"

    def test_multi_number_map_populated(self, monkeypatch):
        monkeypatch.setenv("PHONE_NUMBER_MAP", "id1:tok1:area1:site1,id2:tok2:area2:site2")
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "tok")
        monkeypatch.setenv("BACKEND_API_KEY", "key")
        monkeypatch.setenv("GCS_BUCKET", "bucket")

        config = WhatsAppConfig.from_env()
        assert "id1" in config.phone_number_map
        assert "id2" in config.phone_number_map
        assert config.phone_number_map["id1"].area == "area1"
        assert config.phone_number_map["id2"].site == "site2"
