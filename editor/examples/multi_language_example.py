"""
Example demonstrating multi-language AST editing capabilities
"""

import asyncio
import os
import tempfile
from pathlib import Path

from editor.strategies import (
    get_editor_for_file, get_language_info, get_supported_languages,
    editor_factory
)
from editor.interfaces import EditRequest, EditOperationType, EditOptions


async def create_sample_files():
    """Create sample files in different languages"""
    files = {}
    
    # Python sample
    python_code = '''
def hello_world():
    print("Hello, World!")

class Calculator:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        return a * b

if __name__ == "__main__":
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"5 + 3 = {result}")
'''
    
    # JavaScript sample
    javascript_code = '''
function helloWorld() {
    console.log("Hello, World!");
}

class Calculator {
    add(a, b) {
        return a + b;
    }
    
    multiply(a, b) {
        return a * b;
    }
}

const calc = new Calculator();
const result = calc.add(5, 3);
console.log(`5 + 3 = ${result}`);
'''
    
    # TypeScript sample
    typescript_code = '''
interface Calculable {
    add(a: number, b: number): number;
    multiply(a: number, b: number): number;
}

class Calculator implements Calculable {
    add(a: number, b: number): number {
        return a + b;
    }
    
    multiply(a: number, b: number): number {
        return a * b;
    }
}

const calc: Calculator = new Calculator();
const result: number = calc.add(5, 3);
console.log(`5 + 3 = ${result}`);
'''
    
    # Rust sample
    rust_code = '''
struct Calculator;

impl Calculator {
    fn new() -> Self {
        Calculator
    }
    
    fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }
    
    fn multiply(&self, a: i32, b: i32) -> i32 {
        a * b
    }
}

fn main() {
    let calc = Calculator::new();
    let result = calc.add(5, 3);
    println!("5 + 3 = {}", result);
}
'''
    
    # Create temporary files
    temp_dir = tempfile.mkdtemp()
    
    files['python'] = os.path.join(temp_dir, 'calculator.py')
    files['javascript'] = os.path.join(temp_dir, 'calculator.js')
    files['typescript'] = os.path.join(temp_dir, 'calculator.ts')
    files['rust'] = os.path.join(temp_dir, 'calculator.rs')
    
    with open(files['python'], 'w') as f:
        f.write(python_code)
    
    with open(files['javascript'], 'w') as f:
        f.write(javascript_code)
    
    with open(files['typescript'], 'w') as f:
        f.write(typescript_code)
    
    with open(files['rust'], 'w') as f:
        f.write(rust_code)
    
    return files


async def demonstrate_language_detection():
    """Demonstrate automatic language detection"""
    print("=== Language Detection Demo ===")
    
    files = await create_sample_files()
    
    for lang, file_path in files.items():
        lang_info = get_language_info(file_path)
        print(f"\nFile: {Path(file_path).name}")
        print(f"Detected language: {lang_info['name'] if lang_info else 'Unknown'}")
        
        if lang_info:
            print(f"Parser: {lang_info['parser_library']}")
            print(f"Formatter: {lang_info['formatter']}")
            print(f"Linter: {lang_info['linter']}")


async def demonstrate_editor_selection():
    """Demonstrate automatic editor selection"""
    print("\n=== Editor Selection Demo ===")
    
    files = await create_sample_files()
    
    for lang, file_path in files.items():
        print(f"\nFile: {Path(file_path).name}")
        
        # Get editor capabilities
        capabilities = editor_factory.get_editor_capabilities(file_path)
        print(f"Capabilities: {capabilities}")
        
        # Get appropriate editor
        editor = get_editor_for_file(file_path, preferred_type='ast')
        print(f"Selected editor: {editor.__class__.__name__}")
        
        lang_name = getattr(editor, 'get_language_name', lambda: 'Unknown')()
        print(f"Handles language: {lang_name}")


async def demonstrate_ast_analysis():
    """Demonstrate AST analysis for different languages"""
    print("\n=== AST Analysis Demo ===")
    
    files = await create_sample_files()
    
    for lang, file_path in files.items():
        print(f"\nAnalyzing {Path(file_path).name}...")
        
        try:
            editor = get_editor_for_file(file_path, preferred_type='ast')
            
            analyze_ast_method = getattr(editor, 'analyze_ast', None)
            if analyze_ast_method:
                analysis = await analyze_ast_method(file_path)
                print(f"Functions found: {len(analysis.get('functions', []))}")
                print(f"Classes found: {len(analysis.get('classes', []))}")
                print(f"Complexity score: {analysis.get('complexity', 0)}")
                
                # Show function names
                functions = analysis.get('functions', [])
                if functions:
                    func_names = [f['name'] for f in functions]
                    print(f"Function names: {func_names}")
            else:
                print("AST analysis not available for this editor")
                
        except Exception as e:
            print(f"Error analyzing {lang}: {e}")


async def demonstrate_ast_transformation():
    """Demonstrate AST transformations"""
    print("\n=== AST Transformation Demo ===")
    
    files = await create_sample_files()
    
    # Example: Rename function in Python file
    python_file = files['python']
    print(f"\nTransforming Python file: {Path(python_file).name}")
    
    try:
        editor = get_editor_for_file(python_file, preferred_type='ast')
        
        # Create edit request to rename function
        request = EditRequest(
            file_path=python_file,
            operation_type=EditOperationType.AST,
            target='{"type": "rename_function"}',
            content='{"old_name": "hello_world", "new_name": "greet_user"}',
            options=EditOptions(create_backup=True)
        )
        
        # Apply transformation
        result = await editor.edit(request)
        
        if result.success:
            print("✓ Function renamed successfully")
            print(f"Lines changed: {result.lines_changed}")
            print(f"Backup created: {result.backup_path}")
            if result.diff:
                print("Diff preview:")
                print(result.diff[:200] + "..." if len(result.diff) > 200 else result.diff)
        else:
            print(f"✗ Transformation failed: {result.error}")
            
    except Exception as e:
        print(f"Error during transformation: {e}")


async def demonstrate_extensibility():
    """Demonstrate how to add support for new languages"""
    print("\n=== Extensibility Demo ===")
    
    # Show current supported languages
    supported = get_supported_languages()
    print("Currently supported languages:")
    for lang, extensions in supported.items():
        print(f"  {lang}: {extensions}")
    
    print("\nTo add a new language (e.g., Go):")
    print("1. Create a new editor class extending BaseASTEditor or TreeSitterEditor")
    print("2. Implement required methods (parse_file, transform_ast, etc.)")
    print("3. Register it with the factory:")
    print("   register_custom_editor(GoEditor, {'.go'})")
    print("4. Register language info:")
    print("   register_custom_language('Go', {")
    print("       'extensions': ['.go'],")
    print("       'parser_type': 'tree-sitter',")
    print("       'parser_library': 'tree-sitter-go'")
    print("   })")


async def main():
    """Run all demonstrations"""
    print("Multi-Language AST Editor Demo")
    print("=" * 50)
    
    await demonstrate_language_detection()
    await demonstrate_editor_selection()
    await demonstrate_ast_analysis()
    await demonstrate_ast_transformation()
    await demonstrate_extensibility()
    
    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nNote: Some features require additional dependencies:")
    print("- tree-sitter: pip install tree-sitter")
    print("- tree-sitter-javascript: pip install tree-sitter-javascript")
    print("- tree-sitter-typescript: pip install tree-sitter-typescript")
    print("- tree-sitter-rust: pip install tree-sitter-rust")


if __name__ == "__main__":
    asyncio.run(main()) 