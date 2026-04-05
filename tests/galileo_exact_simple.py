"""Galileo 落体 — 精确枚举计算 belief.

不依赖任何库，纯 Python 实现。
枚举所有 2^10 = 1024 种状态，直接算每个命题为真的概率。
"""

from itertools import product

# ============================================================
# 1. 定义变量（10 个二值命题）
# ============================================================
VARS = ["A", "V", "O_daily", "O_media", "O_air", "T1", "T2", "A_vac", "S_vac", "E"]

# 先验：观测到的事实 = 0.95，未知命题 = 0.5
PRIOR = {
    "A": 0.5,  # 重者更快（待定）
    "V": 0.5,  # 真空等速（待定）
    "O_daily": 0.95,  # 日常观测（已观测）
    "O_media": 0.95,  # 介质观测（已观测）
    "O_air": 0.95,  # 空气观测（已观测）
    "T1": 0.5,  # 拖拽论证（待定）
    "T2": 0.5,  # 总重论证（待定）
    "A_vac": 0.5,  # 真空中重者更快（待定）
    "S_vac": 0.95,  # 真空=零密度（定义性）
    "E": 0.95,  # 斜面实验（已观测）
}


# ============================================================
# 2. 定义因子（8 条规则）
# ============================================================
# 每个因子是一个函数：接收所有变量的取值，返回一个分数


def ent(s, premises, conclusion, p=0.99):
    """Entailment: 前提全真时，结论应为真。"""
    print("premises, conclusion", premises, conclusion)
    if all(s[v] == 1 for v in premises):
        return p if s[conclusion] == 1 else (1 - p)
    return 1.0


def contradiction(s, a, b, p=0.95):
    """Contradiction: 两个不能同时为真。"""
    if s[a] == 1 and s[b] == 1:
        return 1 - p  # 惩罚
    return 1.0


FACTORS = [
    lambda s: ent(s, ["O_daily"], "A", p=0.70),  # W1: 日常观测→重者更快
    lambda s: ent(s, ["A"], "T1"),  # A→T1 (蕴含)
    lambda s: ent(s, ["A"], "T2"),  # A→T2 (蕴含)
    lambda s: contradiction(s, "T1", "T2"),  # T1⊗T2 (矛盾)
    lambda s: ent(s, ["A", "S_vac"], "A_vac"),  # A+S_vac→A_vac (蕴含)
    lambda s: contradiction(s, "A_vac", "V"),  # A_vac⊗V (矛盾)
    lambda s: ent(s, ["O_media", "O_air"], "V", p=0.70),  # W2: 介质观测→真空等速
    lambda s: ent(s, ["E"], "V", p=0.75),  # W3: 斜面实验→等速下落
]


# ============================================================
# 3. 对每个状态打分
# ============================================================
# 一个"状态"就是 10 个变量各取 0 或 1 的一种组合
# 分数 = 所有变量的先验 × 所有因子的打分

scores = {}  # state_tuple -> score

for vals in product([0, 1], repeat=len(VARS)):
    print("vals", vals)
    state = dict(zip(VARS, vals))
    print("state", state)

    # 先验贡献
    score = 1.0
    for var in VARS:
        pi = PRIOR[var]
        score *= pi if state[var] == 1 else (1 - pi)

    # 因子贡献
    for factor in FACTORS:
        score *= factor(state)

    scores[vals] = score

# ============================================================
# 4. 归一化 → 概率分布
# ============================================================
Z = sum(scores.values())  # 配分函数

# ============================================================
# 5. 算边缘概率（belief）
# ============================================================
# 对每个变量，把它=1 的所有状态的概率加起来

belief = {}
for vi, var in enumerate(VARS):
    print("vi, var", vi, var)
    total = 0.0
    for vals, score in scores.items():
        if vals[vi] == 1:
            total += score / Z
    belief[var] = total

# ============================================================
# 6. 输出
# ============================================================
print(f"总状态数: {len(scores)}")
print(f"配分函数 Z = {Z:.6e}")
print()
print(f"{'变量':<15} {'先验':>8} {'Belief':>10}")
print("-" * 35)
for var in VARS:
    arrow = (
        "↑"
        if belief[var] > PRIOR[var] + 0.01
        else ("↓" if belief[var] < PRIOR[var] - 0.01 else "→")
    )
    print(f"{var:<15} {PRIOR[var]:>8.3f} {belief[var]:>10.6f}  {arrow}")

print()
print("关键结论:")
print(f"  A(重者更快)  = {belief['A']:.4f}  ← 被压到很低")
print(f"  V(真空等速)  = {belief['V']:.4f}  ← 被推到很高")
