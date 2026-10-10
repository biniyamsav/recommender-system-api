import json
import logging

from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger(__name__)
client = AsyncGroq(api_key=settings.GROQ_API_KEY)


def _fallback_recommendations(product_list: list[dict]) -> list[dict]:
    fallback: list[dict] = []
    for product in product_list or []:
        if not isinstance(product, dict):
            continue
        product_id = product.get("product_id") or product.get("id")
        if product_id is None:
            continue
        try:
            parsed_id = int(product_id)
        except (TypeError, ValueError):
            continue
        fallback.append({"product_id": parsed_id, "score": 0.50})
    return fallback





async def get_llm_reranked_scores(
    user_profile: dict,
    product_list: list[dict],
    model_name: str = settings.GROQ_MODEL,
) -> list[dict]:
    """
    Sends candidate products and user profile context to Groq for relevance scoring.
    Returns a validated list of {product_id, score} dictionaries or a graceful fallback.
    """
    if not isinstance(user_profile, dict):
        user_profile = {}
    if not isinstance(product_list, list):
        product_list = []
    if not product_list:
        return []

    valid_product_ids = {
        product_id
        for product in product_list
        if isinstance(product, dict)
        for product_id in (product.get("product_id", product.get("id")),)
        if isinstance(product_id, int) and not isinstance(product_id, bool)
    }

    prompt = f"""
    Given the user's category interaction profile (view duration in seconds and purchase spend in USD):
    {json.dumps(user_profile)}

    Score and rank ALL products in this candidate list from most relevant to least relevant:
    {json.dumps(product_list)}

    Return ONLY a JSON object with a key "recommendations" containing a list of objects for all candidates, each having:
    - "product_id": integer
    - "score": float from 0.00 to 1.00
    """

    try:
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content
        parsed_output = json.loads(raw_content)
        recommendations = parsed_output.get("recommendations", [])

        if not isinstance(recommendations, list):
            raise ValueError("Invalid Groq response format")

        validated: list[dict] = []
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            product_id = item.get("product_id")
            score = item.get("score")
            if (
                not isinstance(product_id, int)
                or isinstance(product_id, bool)
                or product_id not in valid_product_ids
            ):
                continue
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                validated.append(
                    {
                        "product_id": product_id,
                        "score": max(0.0, min(1.0, float(score))),
                    }
                )

        if validated:
            return validated
        raise ValueError("No valid recommendations returned")
    except Exception as exc:
        logger.exception("Groq reranker failed; using fallback recommendation scores: %s", exc)
        return _fallback_recommendations(product_list)
