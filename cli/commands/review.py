"""gaia review — LLM-powered claim review."""

import asyncio

import typer

from cli.commands.claim import find_package_dir
from cli.config import load_user_config
from cli.llm_client import _call_llm
from cli.package import load_all_claims
from cli.review_skill import format_review_input, load_skill_prompt, parse_review_output


def review_command(claim_ids: list[int] | None = None):
    """Review claims using LLM."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)
    all_claims_map = {c["id"]: c for c in claims}
    config = load_user_config()
    review_config = config.get("review", {})
    model = review_config.get("model", "claude-sonnet-4-20250514")
    concurrency = review_config.get("concurrency", 5)
    skill_version = review_config.get("skill_version", "v1.0")

    # Select claims to review
    if claim_ids:
        to_review = [all_claims_map[cid] for cid in claim_ids if cid in all_claims_map]
    else:
        # Review all claims that have premises (skip leaf axioms/observations)
        to_review = [c for c in claims if c.get("premise")]

    if not to_review:
        typer.echo("No claims to review.")
        return

    typer.echo(f"Reviewing {len(to_review)} claim(s) with {model}...")

    # Run reviews
    results = asyncio.run(
        _review_batch(to_review, all_claims_map, model, skill_version, concurrency)
    )

    # Print results table
    typer.echo(f"\n{'Claim':>6} | {'Score':>5} | Issue")
    typer.echo("-" * 50)
    for claim, result in zip(to_review, results):
        issues = []
        if result.get("downgraded_premises"):
            issues.append(f"downgraded: {result['downgraded_premises']}")
        if result.get("suggested_premise"):
            issues.append(f"suggested: {result['suggested_premise']}")
        issue_str = "; ".join(issues) if issues else "\u2014"
        typer.echo(f"{claim['id']:>6} | {result['score']:.2f}  | {issue_str}")

    # Save results
    from cli.review_store import save_review

    for claim, result in zip(to_review, results):
        save_review(pkg_dir, claim["id"], result, model, skill_version)
    typer.echo(f"\nReview results saved to {pkg_dir / '.gaia' / 'reviews'}")


async def _review_batch(claims, all_claims_map, model, skill_version, concurrency):
    """Review a batch of claims concurrently."""
    sem = asyncio.Semaphore(concurrency)
    system_prompt = load_skill_prompt(skill_version)

    async def _review_one(claim):
        async with sem:
            user_prompt = format_review_input(claim, all_claims_map)
            raw = await _call_llm(system_prompt, user_prompt, model)
            return parse_review_output(raw)

    tasks = [_review_one(c) for c in claims]
    return await asyncio.gather(*tasks)
