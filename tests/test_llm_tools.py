"""
LLM 本地工具函数单元测试 (get_current_weather, get_system_status)
"""
from unittest.mock import patch

from app.services.llm_service import get_current_weather, get_system_status


class TestWeatherTool:
    def test_known_city_beijing(self):
        result = get_current_weather("北京")
        assert "晴天" in result
        assert "25°C" in result

    def test_known_city_shanghai(self):
        result = get_current_weather("上海")
        assert "多云" in result
        assert "28°C" in result

    def test_known_city_guangzhou(self):
        result = get_current_weather("广州")
        assert "小雨" in result
        assert "26°C" in result

    def test_unknown_city_returns_default(self):
        result = get_current_weather("火星")
        assert "未知" in result
        assert "20°C" in result

    def test_empty_location(self):
        result = get_current_weather("")
        assert "未知" in result


class TestSystemStatusTool:
    def test_returns_cpu_info(self):
        result = get_system_status()
        assert "CPU 使用率" in result

    def test_returns_memory_info(self):
        result = get_system_status()
        assert "内存使用率" in result

    def test_returns_disk_info(self):
        result = get_system_status()
        assert "磁盘使用率" in result

    def test_returns_non_empty_string(self):
        result = get_system_status()
        assert isinstance(result, str)
        assert len(result) > 0
