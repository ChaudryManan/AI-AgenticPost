import asyncio
from smauto.nodes.text.image_assembly import _generate_visual_brief

async def main():
    state = {"topic": "Why RAG beats fine-tuning for customer support"}
    draft = {
        "hook": "Your support bot is confidently wrong.",
        "body": (
            "Fine-tuning bakes knowledge into a static model. The moment "
            "your policies change, the model is out of date. RAG retrieves "
            "the current answer before responding — no retraining required."
        ),
        "cta": "Try the demo.",
    }
    brief = await _generate_visual_brief(state, draft, state["topic"])
    print()
    print("PROMPT:")
    print(" ", brief["prompt"])
    print()
    print("NEGATIVE:")
    print(" ", brief["negative"])
    print()
    print("RATIONALE:")
    print(" ", brief["rationale"])

asyncio.run(main())