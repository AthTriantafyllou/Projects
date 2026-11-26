# app/pipelines/llm_helpers.py

import os
import json
from openai import AsyncOpenAI
import base64


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def summarize_chunk(text: str) -> str:
    """
    Universal summarization for any type of document.
    Produces a neutral, domain-agnostic summary suitable for
    legal, educational, creative, technical, or general content.
    """

    prompt = f"""
You are a universal summarization assistant.

Summarize the following text into 3–5 concise bullet points.
- DO NOT assume it is a story.
- DO NOT invent events, people, or locations.
- Capture only what is explicitly present in the text.
- Focus on the most important ideas, facts, arguments, or claims.
- Preserve domain-specific information (legal, technical, educational, narrative).

Text:
{text}
"""

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You produce accurate, faithful summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return resp.choices[0].message.content.strip()



async def extract_entities(text: str):
    """
    SAFE entity extraction: 
    - Always returns valid JSON
    - Never crashes on malformed LLM output
    - Limits length to prevent runaway tokens
    """

    SAFE_PROMPT = """
Extract named entities from the text.

RETURN ONLY strict JSON in the following format:
{
  "entities": [
    {"text": "...", "type": "..."}
  ]
}

Allowed types:
- PERSON
- LOCATION
- ORGANIZATION
- DATE
- EVENT
- OBJECT
- CONCEPT

CRITICAL RULES:
- Return ONLY JSON.
- NO explanation.
- NO markdown.
- NO comments.
- NO text before/after JSON.
If you cannot find entities, return:
{"entities": []}
"""

    # safeguard if text too large
    chunk = text[:6000]

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Return ONLY JSON."},
            {"role": "user", "content": SAFE_PROMPT + "\n\nTEXT:\n" + chunk},
        ],
        temperature=0,
        max_tokens=200,
    )

    raw = resp.choices[0].message.content.strip()

    # ultimate failsafe
    if not raw.startswith("{"):
        return []

    try:
        data = json.loads(raw)
        entities = data.get("entities", [])
        result = []
        for ent in entities:
            if isinstance(ent, dict) and "text" in ent and "type" in ent:
                result.append({
                    "text": str(ent["text"]).strip(),
                    "type": str(ent["type"]).upper().strip(),
                })
        return result
    except:
        return []


# app/pipelines/llm_helpers.py



client = AsyncOpenAI()

async def describe_image(image_bytes: bytes) -> str:
    """
    Gives a concise but information-rich description of the image.
    Must include artist names, artwork titles, places, people if recognizable.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Give a concise description of this image for educational use. "
                            "If the image depicts a known artwork, artist, historical figure, "
                            "place or event, explicitly name them."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=180,
    )

    return resp.choices[0].message.content.strip()


async def ocr_image(image_bytes: bytes) -> str:
    """
    Extracts visible text, labels and mathematical expressions.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract any visible text, labels and mathematical expressions "
                            "exactly as they appear in the image. "
                            "Do not add explanations."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=220,
    )

    return resp.choices[0].message.content.strip()


async def extract_latex_from_image(image_bytes: bytes) -> str:
    """
    Προσπαθεί να αποδώσει την εξίσωση σε LaTeX ή όσο πιο ‘καθαρό’ math text γίνεται.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "If this image contains a mathematical formula, "
                            "return it in LaTeX or plain text math. "
                            "If not, return 'NO_EQUATION'."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}" }},
                ],
            }
        ],
        max_tokens=120,
    )
    return resp.choices[0].message.content.strip()
    