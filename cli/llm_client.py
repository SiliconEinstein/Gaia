"""LLM client for claim review. Uses litellm for model-agnostic API calls."""

import asyncio

from cli.review_skill import format_review_input, load_skill_prompt, parse_review_output


async def _call_llm(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call LLM via litellm (supports OpenAI, Anthropic, etc.)."""
    import litellm

    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content


async def review_claim(
    claim: dict,
    all_claims: dict[int, dict],
    model: str = "claude-sonnet-4-20250514",
    skill_version: str = "v1.0",
) -> dict:
    """Review a single claim using the review skill prompt."""
    system_prompt = load_skill_prompt(skill_version)
    user_prompt = format_review_input(claim, all_claims)
    raw_output = await _call_llm(system_prompt, user_prompt, model)
    return parse_review_output(raw_output)


async def review_claims_concurrent(
    claims: list[dict],
    all_claims: dict[int, dict],
    model: str = "claude-sonnet-4-20250514",
    concurrency: int = 5,
) -> list[dict]:
    """Review multiple claims concurrently with semaphore-based throttling."""
    sem = asyncio.Semaphore(concurrency)

    async def _review_one(claim):
        async with sem:
            return await review_claim(claim, all_claims, model)

    tasks = [_review_one(c) for c in claims]
    return await asyncio.gather(*tasks)
