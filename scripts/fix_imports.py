#!/usr/bin/env python3
"""Fix import sorting and unused imports."""

import re
from pathlib import Path
from typing import List


def sort_imports(imports: List[str]) -> List[str]:
    """Sort imports according to PEP8/isort standards."""
    # Group imports into categories
    stdlib_imports = []
    third_party_imports = []
    local_imports = []
    
    third_party_modules = {'typer', 'rich', 'yaml', 'pydantic', 'aiohttp'}
    
    for imp in imports:
        # Clean up the import string
        imp = imp.strip()
        if not imp:
            continue
            
        # Get the base module name
        if imp.startswith('from '):
            base_module = imp.split()[1].split('.')[0]
        else:
            base_module = imp.split()[1].split('.')[0]
            
        # Categorize the import
        if base_module in third_party_modules:
            third_party_imports.append(imp)
        elif base_module.startswith('.'):
            local_imports.append(imp)
        else:
            stdlib_imports.append(imp)
    
    # Sort each category
    stdlib_imports.sort()
    third_party_imports.sort()
    local_imports.sort()
    
    # Combine with appropriate spacing
    sorted_imports = []
    if stdlib_imports:
        sorted_imports.extend(stdlib_imports)
        sorted_imports.append('')
    if third_party_imports:
        sorted_imports.extend(third_party_imports)
        sorted_imports.append('')
    if local_imports:
        sorted_imports.extend(local_imports)
        sorted_imports.append('')
    
    return sorted_imports


def process_file(file_path: Path) -> None:
    """Process a single file to fix import sorting."""
    content = file_path.read_text()
    
    # Find the import block
    import_block_match = re.search(
        r'((?:import|from)\s+[^\n]+\n)+',
        content
    )
    
    if not import_block_match:
        return
        
    import_block = import_block_match.group(0)
    import_lines = [line for line in import_block.split('\n') if line.strip()]
    
    # Sort imports
    sorted_imports = sort_imports(import_lines)
    
    # Replace old imports with sorted ones
    new_content = content.replace(
        import_block,
        '\n'.join(sorted_imports) + '\n'
    )
    
    # Write back if changed
    if new_content != content:
        file_path.write_text(new_content)
        print(f"✅ Fixed imports in {file_path}")


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent
    
    # Process Python files
    for path in root.rglob("*.py"):
        try:
            process_file(path)
        except Exception as e:
            print(f"❌ Error processing {path}: {e}")


if __name__ == "__main__":
    main()