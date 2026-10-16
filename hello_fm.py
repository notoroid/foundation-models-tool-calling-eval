import asyncio

import apple_fm_sdk as fm


@fm.generable("Suggested items")
class ItemsSuggestion:
    item_names: list[str] = fm.guide("Names of the suggested items")


async def main() -> None:
    model = fm.SystemLanguageModel()
    is_available, reason = model.is_available()
    if not is_available:
        print(f"Foundation Model is not available: {reason}")
        return

    session = fm.LanguageModelSession(instructions="簡潔に日本語で答えてください。")
    print(await session.respond("こんにちは。自己紹介をしてください。"))

    # Guided generation
    session = fm.LanguageModelSession()
    result = await session.respond(
        "Suggest three grocery items for a curry dinner.",
        generating=ItemsSuggestion,
    )
    print(result.item_names)


if __name__ == "__main__":
    asyncio.run(main())
