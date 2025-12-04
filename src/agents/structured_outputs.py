from pydantic import BaseModel, Field
from typing import Literal, Optional


class ImageSelection(BaseModel):
    image_number: int = Field(..., description="Номер изображения. Отсчет изображений ведется от 0."
                                               "Если ни одно изображение не подошло согласно инструкции и согласно посту, то верни -1")

    reason: str = Field(..., description = "Причина выбора изображения или причина по которой все изображения отклонены")
    

class FilterOutput(BaseModel):
    good_news: bool = Field(..., description="True - если новость подходит чтобы её переписали"\
                                            "False новость мусорная, содержит какие - то непонятные факты, отсутствует новость или есть какой - то странный отве,"\
                                            "например, что кто - то готов переписать пост и похожее"\
                                            "не имеет достаточно контекста для понимания.")
