from fastapi import APIRouter

from api.schemas import VoiceOption
from utils.audio import AVAILABLE_VOICES

router = APIRouter(tags=["voices"])

_VERIFIED = {"Fenrir", "Puck"}


@router.get("/voices", response_model=list[VoiceOption])
def list_voices() -> list[VoiceOption]:
    return [VoiceOption(name=v, verified=v in _VERIFIED) for v in AVAILABLE_VOICES]
