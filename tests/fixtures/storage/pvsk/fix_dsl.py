"""Fix DSL issues in all PVSK packages: convert setting/question used as strategy premises to claim."""

import re
from pathlib import Path

BASE = Path("/personal/Gaia/tests/fixtures/storage/pvsk")

# Find all __init__.py files in pvsk packages
for init_file in sorted(BASE.glob("pvsk-*/src/pvsk_*/__init__.py")):
    if init_file.parent.parent.parent.name == "pvsk-meta-gaia":
        continue

    content = init_file.read_text()
    original = content

    # Track variable names that are setting() or question() and used in support/deduction premises
    # Pattern: varname = setting(...) or varname = question(...)
    setting_vars = set()
    question_vars = set()
    for m in re.finditer(r"^(\w+)\s*=\s*setting\(", content, re.MULTILINE):
        setting_vars.add(m.group(1))
    for m in re.finditer(r"^(\w+)\s*=\s*question\(", content, re.MULTILINE):
        question_vars.add(m.group(1))

    if not setting_vars and not question_vars:
        continue

    # Check which are used in strategy calls (support/deduction/contradiction premises)
    problem_settings = set()
    problem_questions = set()

    for var in setting_vars:
        # Check if var appears inside a list argument (strategy premises)
        if re.search(rf"\[{var}\]|\[{var},|,\s*{var}\]|,\s*{var}\s*\]", content):
            problem_settings.add(var)

    for var in question_vars:
        if re.search(rf"\[{var}\]|\[{var},|,\s*{var}\]|,\s*{var}\s*\]", content):
            problem_questions.add(var)

    if not problem_settings and not problem_questions:
        continue

    # Fix: convert setting(...) used as premise to claim(..., prior=0.7)
    for var in problem_settings:
        content = re.sub(
            rf"({var}\s*=\s*)setting\(",
            rf"\1claim(",
            content,
        )
        # Add prior if not present - insert before the closing )
        # This is tricky since setting doesn't have prior. We need to add one.
        # Find the specific claim line and add prior
        pattern = rf"({var}\s*=\s*claim\()(.*?)(\)\s*$)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match and "prior=" not in match.group(0):
            # Add prior before the closing paren
            old_line = match.group(0).rstrip()
            content = content.replace(old_line, old_line[:-1] + ",\n    prior=0.70,\n)")

    # Fix: convert question(...) used as premise to claim(..., prior=0.5)
    for var in problem_questions:
        content = re.sub(
            rf"({var}\s*=\s*)question\(",
            rf"\1claim(",
            content,
        )
        match = re.search(rf"({var}\s*=\s*claim\()(.*?)(\)\s*$)", content, re.MULTILINE | re.DOTALL)
        if match and "prior=" not in match.group(0):
            old_line = match.group(0).rstrip()
            content = content.replace(old_line, old_line[:-1] + ",\n    prior=0.50,\n)")

    if content != original:
        init_file.write_text(content)
        changes = []
        if problem_settings:
            changes.append(f"settings→claims: {', '.join(problem_settings)}")
        if problem_questions:
            changes.append(f"questions→claims: {', '.join(problem_questions)}")
        print(f"Fixed {init_file.parent.parent.parent.name}: {'; '.join(changes)}")
    else:
        print(f"OK {init_file.parent.parent.parent.name}")
