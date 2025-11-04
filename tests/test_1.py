import asyncio
from ai.example import main as ai_main
from editor.example_usage import main as editor_main

def test_ai():
    asyncio.run(ai_main())

# def test_editor():
#     editor_main()
