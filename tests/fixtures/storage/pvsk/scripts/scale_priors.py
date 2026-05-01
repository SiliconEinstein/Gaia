"""Lower meta proposition priors and strategy propagation strength.

Changes:
1. Meta priors: 0.3/0.2/0.15 → 0.05/0.03/0.01
2. Strategy priors (support/deduction): scale down by factor 0.6
3. Claim priors: unchanged (keep evidence strength)
"""

import re
from pathlib import Path

BASE = Path("/personal/Gaia/tests/fixtures/storage/pvsk")
STRATEGY_SCALE = 0.6

# ---------------------------------------------------------------------------
# 1. Lower meta proposition priors
# ---------------------------------------------------------------------------
META_FILE = BASE / "pvsk-meta-gaia" / "src" / "pvsk_meta" / "__init__.py"
META_NEW_PRIORS = {
    "p_viability": 0.05,
    "p_efficiency": 0.03,
    "p_improvement": 0.05,
    "p_stability": 0.03,
    "p_industrialization": 0.01,
}

meta_content = META_FILE.read_text()
for prop, new_prior in META_NEW_PRIORS.items():
    pattern = rf'(prior=)\s*[\d.]+(\s*,?\s*\))'
    # Only replace the prior for this specific prop
    prop_block = re.search(
        rf'({prop}\s*=\s*claim\(.*?)(prior=)\s*[\d.]+',
        meta_content,
        re.DOTALL,
    )
    if prop_block:
        old_prior_text = prop_block.group(0)
        new_prior_text = old_prior_text.rsplit("prior=", 1)[0] + f"prior={new_prior}"
        meta_content = meta_content.replace(old_prior_text, new_prior_text)

META_FILE.write_text(meta_content)
print(f"Updated meta priors: {META_NEW_PRIORS}")

# ---------------------------------------------------------------------------
# 2. Scale strategy prior in all paper packages
# ---------------------------------------------------------------------------
# Approach: parse each file into strategy blocks vs non-strategy blocks.
# In strategy blocks (support/deduction), scale prior= values.

changed_count = 0
for init_file in sorted(BASE.glob("pvsk-*/src/pvsk_*/__init__.py")):
    if init_file.parent.parent.parent.name == "pvsk-meta-gaia":
        continue

    content = init_file.read_text()
    original = content

    # Find all support(...) and deduction(...) blocks and scale their priors
    # Strategy: find each top-level support/deduction call, extract it, scale priors within

    result = []
    pos = 0
    while pos < len(content):
        # Find next support( or deduction(
        match = re.search(r'(?m)^(support|deduction)\s*\(', content[pos:])
        if not match:
            result.append(content[pos:])
            break

        # Add everything before this match
        result.append(content[pos:pos + match.start()])

        # Find the matching closing paren
        start = pos + match.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        block = content[start:end]

        # Scale all prior= values in this block
        def scale_prior(m):
            val = float(m.group(1))
            new_val = max(round(val * STRATEGY_SCALE, 3), 0.1)
            return f"prior={new_val}"

        scaled_block = re.sub(r'prior=\s*([\d.]+)', scale_prior, block)
        result.append(scaled_block)
        pos = end

    new_content = ''.join(result)
    if new_content != original:
        init_file.write_text(new_content)
        changed_count += 1

print(f"Scaled strategy priors by {STRATEGY_SCALE} in {changed_count} packages")
