"""测试控制流图生成器"""

from app.core.cfg_generator import generate_python_cfg, generate_typescript_cfg


def test_python_cfg_simple():
    """测试简单 Python 函数的 CFG"""
    source = """
def calculate(x):
    if x > 0:
        return x * 2
    else:
        return 0
"""
    dot = generate_python_cfg(source, "calculate")
    assert "digraph calculate" in dot
    assert "if x > 0" in dot
    assert "return" in dot


def test_python_cfg_loop():
    """测试带循环的 Python 函数"""
    source = """
def sum_list(items):
    total = 0
    for item in items:
        total += item
    return total
"""
    dot = generate_python_cfg(source, "sum_list")
    assert "for item in items" in dot
    assert "loop" in dot


def test_python_cfg_while():
    """测试 while 循环"""
    source = """
def countdown(n):
    while n > 0:
        print(n)
        n -= 1
    return "Done"
"""
    dot = generate_python_cfg(source, "countdown")
    assert "while n > 0" in dot
    assert "loop" in dot


def test_python_cfg_try_except():
    """测试 try-except"""
    source = """
def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return 0
"""
    dot = generate_python_cfg(source, "safe_divide")
    assert "try" in dot
    assert "except" in dot


def test_typescript_cfg():
    """测试 TypeScript 函数的 CFG（简化版）"""
    source = """
function greet(name: string): string {
    if (name) {
        return `Hello, ${name}`;
    }
    return "Hello, stranger";
}
"""
    dot = generate_typescript_cfg(source, "greet")
    assert "digraph greet" in dot
    assert "if" in dot or "Entry" in dot
