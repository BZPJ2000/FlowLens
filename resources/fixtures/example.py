def compute(a: int, b: int) -> int:
    return add(a, b)

def add(x: int, y: int) -> int:
    return x + y

class Calc:
    @staticmethod
    def multiply(p: float, q: float) -> float:
        return p * q

def main():
    result = compute(3, 5)
    print(Calc.multiply(result, 2.0))