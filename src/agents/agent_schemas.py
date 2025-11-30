from typing_extensions import TypedDict
import typing as tp

class SourceAgentGraph(TypedDict):

    post: str
    grade: str
    emoji_reactions: dict[str, str]
    generation: str
    search_query: str
    is_meme: bool
    image_url: tp.Optional[str]
    image_num: int
    media_ctx: tp.Optional[str]
    media_links: list[str] 
    good_news: bool