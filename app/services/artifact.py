from __future__ import annotations

from typing import Dict, Optional

import bleach
import markdown

from app.config import settings


def generate_artifact(topic: str, source_text: Optional[str] = None, artifact_type: str = "markdown") -> Dict[str, str]:
    source_text = source_text or (
        "This artifact summarizes the conversation and outlines the core recommendation, evidence, next steps, and a clear takeaway."
    )
    title = topic.strip() or "Growth Summary"
    markdown_document = f"# {title}\n\n## Context\n\n{source_text}\n\n## Key takeaway\n\n- Ground the recommendation in actual customer behavior, not just channel assumptions.\n- Run a few strong experiments instead of a broad, low-signal campaign.\n- Measure the loop that compounds retention and distribution.\n\n## Next steps\n\n1. Identify the highest-leverage customer pain.\n2. Test one acquisition or activation experiment.\n3. Review the loop weekly and decide what to double down on.\n"

    if artifact_type == "markdown":
        return {"type": "markdown", "content": markdown_document}

    clean_tags = [tag.strip() for tag in settings.artifact_allowed_tags.split(",") if tag.strip()]
    allowed_attributes = {}
    for attr in settings.artifact_allowed_attributes.split(","):
        part = attr.strip()
        if part:
            allowed_attributes[part.split("[")[0]] = [p.strip() for p in part.split("[")[1].rstrip("]").split(",") if p.strip()]
    html_document = markdown.markdown(markdown_document)
    sanitized = bleach.clean(
        html_document,
        tags=clean_tags,
        attributes=allowed_attributes,
        strip=True,
    )
    return {"type": "html", "content": sanitized}
