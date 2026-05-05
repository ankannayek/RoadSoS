import os
import re

def fix_conflicts_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if '<<<<<<< HEAD' not in content:
        return

    # Regular expression to match the merge conflict block.
    # The `.*?` between `=======\n` and `>>>>>>>` needs to be optional or non-existent sometimes,
    # so we use `(?:.*?)` and handle the potential for missing newlines if it's empty.
    # Actually, we can just split the file or use a simpler regex.
    # Let's just use re.sub with a regex that matches \n=======\n(?:.*?)\n>>>>>>> [a-f0-9]+
    pattern = re.compile(r'<<<<<<< HEAD\n(.*?)\n=======\n(?:.*?)\n?>>>>>>> [a-f0-9]+(\n|$)', re.DOTALL)
    
    new_content = pattern.sub(r'\1\2', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Fixed conflicts in {filepath}")

def main():
    app_dir = os.path.join(os.path.dirname(__file__), 'app')
    for root, _, files in os.walk(app_dir):
        for file in files:
            if file.endswith('.py'):
                fix_conflicts_in_file(os.path.join(root, file))

    # Also check tests if needed
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
    if os.path.exists(tests_dir):
        for root, _, files in os.walk(tests_dir):
            for file in files:
                if file.endswith('.py'):
                    fix_conflicts_in_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
