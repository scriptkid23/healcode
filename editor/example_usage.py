"""
Example usage of HealCode Editor Module with actual demo.py file
"""

import asyncio
import os
import shutil
from pathlib import Path

from .service import EditorService, EditorConfig
from .interfaces import EditRequest, EditOperationType, EditOptions, RollbackRequest


async def demo_basic_editing():
    """Basic demo: editing demo.py file directly and adding a new function"""
    
    demo_file = "editor/demo.py"  # Directly edit the original file
    
    if not os.path.exists(demo_file):
        print(f"Error: File not found {demo_file}")
        return
    
    try:
        # Initialize editor service
        config = EditorConfig(
            max_concurrent_operations=5,
            allowed_extensions=['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.txt', '.md']
        )
        editor = EditorService(config)
        
        print("🚀 DEMO EDITING DEMO.PY FILE (DIRECT)")
        print("=" * 50)
        
        # Display original file content
        print("📁 Original file content:")
        with open(demo_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(content)
        print("-" * 30)
        
        # Demo 1: Edit specific line
        print("1. 📝 Editing line 2 - changing function logic...")
        result1 = await editor.edit_line(
            file_path=demo_file,
            line_number=2,
            new_content='    return a - b  # Changed from addition to multiplication'
        )
        
        print(f"   ✅ Success: {result1.success}")
        print(f"   📊 Lines changed: {result1.lines_changed}")
        print(f"   🆔 Operation ID: {result1.operation_id}")
        if result1.error:
            print(f"   ❌ Error: {result1.error}")
        if result1.diff:
            print("   📋 Diff:")
            print("   " + "\n   ".join(result1.diff.split('\n')[:10]))
        print()
        
        # Demo 2: Pattern replacement - rename function
        print("2. 🔍 Using pattern to rename function...")
        result2 = await editor.edit_pattern(
            file_path=demo_file,
            pattern=r"def multiply_numbers\(",
            replacement="def multiply_numbers("
        )
        
        print(f"   ✅ Success: {result2.success}")
        print(f"   🎯 Matches found: {result2.metadata.get('matches_found', 0)}")
        print(f"   🆔 Operation ID: {result2.operation_id}")
        if result2.error:
            print(f"   ❌ Error: {result2.error}")
        print()
        
        # Demo 3: Add a new function at the end of the file using editor
        print("3. ➕ Adding new function subtract_numbers at the end of demo.py using editor...")
        new_func = '\ndef subtract_numbers(a, b):\n    return a - b  # New subtract function added by editor\n'
        result3 = await editor.append_block(
            file_path=demo_file,
            content=new_func
        )
        print(f"   ✅ Success: {result3.success}")
        if result3.error:
            print(f"   ❌ Error: {result3.error}")
        print()
        
        # Demo 4: Insert a new function at line 18 using edit_lines
        print("4. 📝 Insert new function my_function at line 18 using edit_lines...")
        func_lines = [
            "def my_function(x):",
            "    return x[::-1]",
            "",
            "mytxt = my_function(\"I wonder how this text looks like backwards\")",
            "",
            "print(mytxt)"
        ]
        start_line = 5
        line_numbers = list(range(start_line, start_line + len(func_lines)))
        result_func = await editor.edit_lines(
            file_path=demo_file,
            line_numbers=line_numbers,
            new_contents=func_lines
        )
        print(f"   ✅ Success: {result_func.success}")
        print(f"   📊 Lines changed: {result_func.lines_changed}")
        if result_func.error:
            print(f"   ❌ Error: {result_func.error}")
        print()
        
        # Demo 5: Display file after editing
        print("5. 📄 File content after editing:")
        with open(demo_file, 'r', encoding='utf-8') as f:
            modified_content = f.read()
        print(modified_content)
        print("-" * 30)
        
        # Demo 5: Check operation status
        print("5. 📊 Checking operation status...")
        status = await editor.get_operation_status(result1.operation_id)
        if status:
            print(f"   🔍 Operation {result1.operation_id[:8]}...")
            print(f"      Status: {status['status']}")
            print(f"      File: {status['file_path']}")
            print(f"      Type: {status['operation_type']}")
            print(f"      Duration: {status.get('duration_seconds', 0):.3f}s")
        print()
        
        # Demo 3: Batch edit/insert lines using edit_lines
        print("3. 📝 Batch edit/insert lines 2, 3, 4 using edit_lines...")
        batch_lines = [2, 3, 4]
        batch_contents = [
            '    return a * b  # Batch: multiplication',
            '    # Inserted by batch edit',
            '    # Another inserted line'
        ]
        result_batch = await editor.edit_lines(
            file_path=demo_file,
            line_numbers=batch_lines,
            new_contents=batch_contents
        )
        print(f"   ✅ Success: {result_batch.success}")
        print(f"   📊 Lines changed: {result_batch.lines_changed}")
        if result_batch.error:
            print(f"   ❌ Error: {result_batch.error}")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def demo_advanced_ast_editing():
    """Advanced demo: AST editing with demo.py"""
    
    demo_file = "editor/demo.py"
    test_file = "editor/demo_ast_test.py"
    
    if not os.path.exists(demo_file):
        print(f"Error: File not found {demo_file}")
        return
    
    # Copy file for testing
    shutil.copy2(demo_file, test_file)
    
    try:
        config = EditorConfig()  # Backup disabled by default
        editor = EditorService(config)
        
        print("🧠 ADVANCED AST EDITING DEMO")
        print("=" * 40)
        
        # Demo 1: AST-based function renaming
        print("1. 🔧 AST: Renaming function add_numbers...")
        
        ast_config = {
            "type": "rename_function",
            "parameters": {
                "old_name": "add_numbers",
                "new_name": "sum_two_values"
            }
        }
        
        result = await editor.edit_file(EditRequest(
            file_path=test_file,
            operation_type=EditOperationType.AST,
            target=str(ast_config),
            content="",
            options=EditOptions(create_backup=True)
        ))
        
        print(f"   ✅ AST Edit success: {result.success}")
        if result.success:
            print(f"   🔄 Transformations applied: {result.metadata.get('transformations_applied', 0)}")
        else:
            print(f"   ❌ Error: {result.error}")
        print()
        
        # Demo 2: Add import statement
        print("2. 📦 AST: Adding import statement...")
        
        ast_config2 = {
            "type": "add_import",
            "parameters": {
                "module": "math",
                "alias": None
            }
        }
        
        result2 = await editor.edit_file(EditRequest(
            file_path=test_file,
            operation_type=EditOperationType.AST,
            target=str(ast_config2),
            content="",
            options=EditOptions(create_backup=True)
        ))
        
        print(f"   ✅ Import success: {result2.success}")
        if not result2.success:
            print(f"   ❌ Error: {result2.error}")
        print()
        
        # Demo 3: Display file after AST modifications
        print("3. 📄 File after AST modifications:")
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print(content)
        except Exception as e:
            print(f"   ❌ Cannot read file: {e}")
        
    except Exception as e:
        print(f"❌ AST demo error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            os.unlink(test_file)
            print(f"🗑️ Deleted AST test file: {test_file}")
        except OSError:
            pass


async def demo_pattern_search_and_replace():
    """Demo pattern search and replace functionality"""
    
    demo_file = "editor/demo.py"
    test_file = "editor/demo_pattern_test.py"
    
    if not os.path.exists(demo_file):
        print(f"Error: File not found {demo_file}")
        return
    
    shutil.copy2(demo_file, test_file)
    
    try:
        config = EditorConfig()  # Backup disabled by default
        editor = EditorService(config)
        
        print("🔍 PATTERN SEARCH & REPLACE DEMO")
        print("=" * 40)
        
        # Get pattern editor
        pattern_editor = editor.strategies[EditOperationType.PATTERN]
        
        # Demo 1: Search patterns before editing
        print("1. 🔍 Searching for function definitions...")
        matches = await pattern_editor.search_pattern(
            test_file,
            r"def\s+(\w+)\s*\(",
            encoding='utf-8'
        )
        
        print(f"   📊 Found {len(matches)} function definitions:")
        for match in matches:
            print(f"      Line {match['line_number']}: {match['match'].strip()}")
        print()
        
        # Demo 2: Search for class definitions
        print("2. 🏗️ Searching for class definitions...")
        class_matches = await pattern_editor.search_pattern(
            test_file,
            r"class\s+(\w+)",
            encoding='utf-8'
        )
        
        print(f"   📊 Found {len(class_matches)} class definitions:")
        for match in class_matches:
            print(f"      Line {match['line_number']}: {match['match'].strip()}")
        print()
        
        # Demo 3: Pattern validation
        print("3. ✅ Validating patterns...")
        
        # Valid pattern
        analysis1 = await pattern_editor.validate_pattern(r"def\s+(\w+)\s*\(")
        print(f"   Pattern 'def\\s+(\\w+)\\s*\\(' - Valid: {analysis1['valid']}")
        
        # Invalid pattern
        analysis2 = await pattern_editor.validate_pattern(r"def\s+(\w+\s*\(")
        print(f"   Pattern 'def\\s+(\\w+\\s*\\(' - Valid: {analysis2['valid']}")
        if not analysis2['valid']:
            print(f"      ❌ Error: {analysis2['error']}")
        print()
        
        # Demo 4: Advanced pattern replacement
        print("4. 🔄 Complex pattern replacement...")
        
        # Add docstring to function
        result = await editor.edit_pattern(
            file_path=test_file,
            pattern=r"(def add_numbers\(a, b\):\n)",
            replacement=r'\1    """Adds two numbers and returns the result"""\n'
        )
        
        print(f"   ✅ Pattern replacement: {result.success}")
        if result.success:
            print(f"   📊 Matches found: {result.metadata.get('matches_found', 0)}")
        print()
        
        # Demo 5: Display results
        print("5. 📄 File after pattern replacements:")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(content)
        
    except Exception as e:
        print(f"❌ Pattern demo error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            os.unlink(test_file)
            print(f"🗑️ Deleted pattern test file: {test_file}")
        except OSError:
            pass


async def demo_concurrent_editing():
    """Demo concurrent editing with file locking"""
    
    demo_file = "editor/demo.py"
    test_files = [f"editor/demo_concurrent_{i}.py" for i in range(3)]
    
    if not os.path.exists(demo_file):
        print(f"Error: File not found {demo_file}")
        return
    
    # Create multiple copies
    for test_file in test_files:
        shutil.copy2(demo_file, test_file)
    
    try:
        config = EditorConfig(
            max_concurrent_operations=10
        )
        editor = EditorService(config)
        
        print("⚡ CONCURRENT EDITING DEMO")
        print("=" * 40)
        
        # Demo: Edit multiple files concurrently
        print("1. 🔄 Editing 3 files concurrently...")
        
        tasks = []
        for i, test_file in enumerate(test_files):
            task = editor.edit_line(
                file_path=test_file,
                line_number=2,
                new_content=f'    return a + b + {i}  # Modified by task {i}'
            )
            tasks.append(task)
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print("   📊 Concurrent editing results:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"      Task {i}: ❌ Error: {result}")
            else:
                print(f"      Task {i}: ✅ Success: {result.success}, Operation: {result.operation_id[:8]}...")
        print()
        
        # Demo 2: List active operations
        print("2. 📋 Active operations:")
        active_ops = await editor.list_active_operations()
        if active_ops:
            for op in active_ops:
                print(f"   - {op['operation_id'][:8]}...: {op['operation_type']} on {op['file_path']}")
        else:
            print("   ✅ No active operations")
        print()
        
        # Demo 3: Display file contents after editing
        print("3. 📄 File contents after concurrent editing:")
        for i, test_file in enumerate(test_files):
            print(f"   File {i+1}:")
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                print("   " + "\n   ".join(content.split('\n')[:5]) + "\n")
            except Exception as e:
                print(f"   ❌ Cannot read file: {e}")
        
    except Exception as e:
        print(f"❌ Concurrent demo error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup all test files
        for test_file in test_files:
            try:
                os.unlink(test_file)
                print(f"🗑️ Deleted: {test_file}")
            except OSError:
                pass


def main():
    """Run all demos"""
    print("🎯 HEALCODE EDITOR MODULE - COMPLETE DEMO")
    print("=" * 60)
    
    print("\n🔥 Running Basic Editing Demo...")
    asyncio.run(demo_basic_editing())
    
    print("\n" + "=" * 60)
    print("🔥 Running Pattern Search & Replace Demo...")
    asyncio.run(demo_pattern_search_and_replace())
    
    print("\n" + "=" * 60)
    print("🔥 Running Concurrent Editing Demo...")
    asyncio.run(demo_concurrent_editing())
    
    print("\n" + "=" * 60)
    print("🔥 Running Advanced AST Editing Demo...")
    asyncio.run(demo_advanced_ast_editing())
    
    print("\n" + "=" * 60)
    print("🎉 ALL DEMOS COMPLETED!")


if __name__ == "__main__":
    main() 