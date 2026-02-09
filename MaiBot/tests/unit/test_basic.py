"""基础测试 - 验证测试框架正常工作"""
import pytest


@pytest.mark.unit
def test_basic_assertion():
    """测试基本断言"""
    assert 1 + 1 == 2


@pytest.mark.unit
def test_string_operations():
    """测试字符串操作"""
    text = "MaiBot"
    assert text.lower() == "maibot"
    assert len(text) == 6


@pytest.mark.unit
def test_list_operations():
    """测试列表操作"""
    items = [1, 2, 3, 4, 5]
    assert len(items) == 5
    assert sum(items) == 15
    assert max(items) == 5


@pytest.mark.unit
def test_dict_operations():
    """测试字典操作"""
    data = {"name": "MaiBot", "version": "0.11.0"}
    assert data["name"] == "MaiBot"
    assert "version" in data


@pytest.mark.unit
async def test_async_function():
    """测试异步函数"""
    import asyncio

    async def async_add(a, b):
        await asyncio.sleep(0.01)
        return a + b

    result = await async_add(2, 3)
    assert result == 5
