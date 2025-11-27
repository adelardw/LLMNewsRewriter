from pydantic import BaseModel, Field
from typing import Literal
from src.agents.prompts import (VERY_COOL_NEWS, COOL_NEWS, NEUTRAL_NEWS, VERY_BAD_NEWS, NO_EMOJI)


class NewsClassifierReactions(BaseModel):
    reaction: Literal[VERY_COOL_NEWS, COOL_NEWS,
                      NEUTRAL_NEWS, VERY_BAD_NEWS, NO_EMOJI] = Field(..., description='Реакция на пост')


class ImageSelection(BaseModel):
    image_number: int = Field(..., description="Номер изображения. Отсчет изображений ведется от 0."
                                               "Если ни одно изображение не подошло согласно инструкции и согласно посту, то верни -1")

    reason: str = Field(..., description = "Причина выбора изображения или причина по которой все изображения отклонены")