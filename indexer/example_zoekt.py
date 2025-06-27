import asyncio

from indexer.zoekt_client import ZoektClient

async def main():
    client = ZoektClient()
    filename = "controls/control-1/main.js"
    text = ".spinner.visible"

    print(f"\n🔍 Search by filename: {filename}")
    results = await client.search_by_filename(filename)
    for i, r in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {r['FileName']} | Repo: {r['Repository']} | Lang: {r['Language']}")
        print(f"  Line {r['LineNumber']} ({r['LineStart']}-{r['LineEnd']}), Score: {r['Score']}")
        print(f"  Content: {r['Content'].strip()}")
        print(f"  Before: {r['Before']} | After: {r['After']} | FileNameMatch: {r['FileNameMatch']}")
        print()

    print(f"\n🔍 Search by text and filename: '{text}' in {filename}")
    results = await client.search_by_text_and_filename(text, filename)
    for i, r in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {r['FileName']} | Repo: {r['Repository']} | Lang: {r['Language']}")
        print(f"  Line {r['LineNumber']} ({r['LineStart']}-{r['LineEnd']}), Score: {r['Score']}")
        print(f"  Content: {r['Content'].strip()}")
        print(f"  Before: {r['Before']} | After: {r['After']} | FileNameMatch: {r['FileNameMatch']}")
        print()

    print(f"\n🔍 Search by text only: '{text}'")
    results = await client.search_by_text(text)
    for i, r in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {r['FileName']} | Repo: {r['Repository']} | Lang: {r['Language']}")
        print(f"  Line {r['LineNumber']} ({r['LineStart']}-{r['LineEnd']}), Score: {r['Score']}")
        print(f"  Content: {r['Content']}")
        print(f"  Before: {r['Before']} | After: {r['After']} | FileNameMatch: {r['FileNameMatch']}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
