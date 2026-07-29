from typing import Optional

from fastapi import APIRouter

from api.db import get_connection
from api.schemas import CustomTopicRequest, TopicSuggestion
from config import POSSIBLE_TOPICS

router = APIRouter(tags=["topics"])


def _usage_counts() -> dict[str, tuple[int, Optional[str]]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT topic, COUNT(*) AS cnt, MAX(created_at) AS last_used "
            "FROM jobs GROUP BY topic"
        ).fetchall()
    return {row["topic"]: (row["cnt"], row["last_used"]) for row in rows}


def _score(times_used: int) -> float:
    # Real, simple heuristic given the trend-scoring engine doesn't exist yet:
    # topics used less recently/often score higher, so generation naturally
    # rotates through the list instead of repeating the same few topics.
    return round(1.0 / (1 + times_used), 3)


@router.get("/topics", response_model=list[TopicSuggestion])
def list_topics() -> list[TopicSuggestion]:
    usage = _usage_counts()
    suggestions = [
        TopicSuggestion(
            topic=topic,
            score=_score(usage.get(topic, (0, None))[0]),
            times_used=usage.get(topic, (0, None))[0],
            last_used_at=usage.get(topic, (0, None))[1],
        )
        for topic in POSSIBLE_TOPICS
    ]
    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions


@router.post("/topics/custom", response_model=TopicSuggestion)
def custom_topic(payload: CustomTopicRequest) -> TopicSuggestion:
    topic = payload.topic.strip()
    times_used, last_used_at = _usage_counts().get(topic, (0, None))
    return TopicSuggestion(
        topic=topic,
        score=_score(times_used),
        times_used=times_used,
        last_used_at=last_used_at,
    )
