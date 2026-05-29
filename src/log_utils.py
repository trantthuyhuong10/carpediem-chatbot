import time


class StageLogger:
    def __init__(self, name="Pipeline"):
        self.name = name
        self.start = time.time()
        self._last = self.start
        self._indent = 0

    def _indent_str(self):
        return "  " * self._indent + "├─ "

    def push(self, stage, detail=""):
        now = time.time()
        elapsed = now - self._last
        total = now - self.start
        self._last = now
        print(f"{self._indent_str()}[{stage}] {detail} ({elapsed:.3f}s | total {total:.3f}s)")

    def section(self, title):
        now = time.time()
        total = now - self.start
        sep = "═" * max(20, 60 - len(title))
        print(f"\n  {sep} {title} {sep}  ({total:.3f}s)")

    def header(self, text):
        bar = "═" * 60
        print(f"\n╔{bar}╗")
        print(f"║  QUERY: {text}")
        print(f"╚{bar}╝")

    def divider(self):
        print("  " + "─" * 54)

    def result_summary(self, results):
        if not results:
            print("  └─ No results")
            return
        print("  └─ Top results:")
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            name = r.get("name", "")
            price = r.get("price", "")
            print(f"       {i}. [{score:.4f}] {name} | {price}")
