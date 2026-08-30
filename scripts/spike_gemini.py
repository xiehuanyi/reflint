"""M0 spike: prove Strands Agent + GeminiModel + tool use works with our key."""

import os

from dotenv import load_dotenv

load_dotenv()

from strands import Agent, tool
from strands.models.gemini import GeminiModel


@tool
def lookup_doi(title: str) -> dict:
    """Look up a paper by title and return its DOI record.

    Args:
        title: the paper title to look up
    """
    return {
        "title": title,
        "doi": "10.9999/fake.123",
        "is_retracted": True,
        "note": "spike fixture",
    }


def main() -> None:
    model = GeminiModel(
        client_args={"api_key": os.environ["GOOGLE_API_KEY"]},
        model_id="gemini-flash-lite-latest",
        params={"temperature": 0.2},
    )
    agent = Agent(
        model=model,
        tools=[lookup_doi],
        system_prompt=(
            "You are a citation auditor. Use the lookup_doi tool to check the "
            "paper the user names, then report in one sentence whether it is "
            "retracted."
        ),
    )
    result = agent("Check the paper 'Attention Is All You Need'.")
    print("\n--- FINAL ---")
    print(result)


if __name__ == "__main__":
    main()
