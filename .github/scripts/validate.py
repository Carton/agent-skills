#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def validate_skill_file(filepath):
    """Validate a SKILL.md file"""
    errors = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.startswith('---'):
        errors.append("Missing frontmatter")
        return errors

    frontmatter_match = re.search(r'^---$(.*?)^---$', content, re.MULTILINE | re.DOTALL)
    if not frontmatter_match:
        errors.append("Invalid frontmatter format")
        return errors

    frontmatter = frontmatter_match.group(1)

    if 'name:' not in frontmatter:
        errors.append("Missing required field: name")

    if 'description:' not in frontmatter:
        errors.append("Missing required field: description")

    return errors


def main():
    skills_dir = Path('skills')

    if not skills_dir.exists():
        print("Error: skills/ directory not found")
        sys.exit(1)

    all_valid = True
    skill_files = list(skills_dir.rglob('SKILL.md'))

    if not skill_files:
        print("Error: No SKILL.md files found")
        sys.exit(1)

    print(f"Found {len(skill_files)} SKILL.md files\n")

    for skill_file in skill_files:
        print(f"Validating {skill_file.as_posix()}")

        errors = validate_skill_file(skill_file)

        if errors:
            for error in errors:
                print(f"  ❌ {error}")
            all_valid = False
        else:
            print(f"  ✅ Valid")
        print()

    if all_valid:
        print("✅ All SKILL.md files are valid!")
        sys.exit(0)
    else:
        print("❌ Validation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
