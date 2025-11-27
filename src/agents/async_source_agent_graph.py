from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from loguru import logger
import asyncio
from src.config import OPEN_ROUTER_API_KEY, TEXT_IMAGE_MODEL, TEXT_GENERATION_MODEL


from src.agents.prompts import (rewiritter_prompt, relevance_prompt, image_selection_prompt,theme_prompt,
                                image_description_prompt, meme_find_prompt,final_prompt,
                                FORBIDDEN_ANSWER)

from src.agents.agent_schemas import SourceAgentGraph
from src.tools.ddgs_web_search import retriever
from src.tgbot.cache import cache_db
from src.agents.utils import redis_update_links, preproc_text_on_banned_org, measure_time_async
from src.tools.google_web_search import get_ddgs_image_loads
from src.tools.utils import rm_img_folders
from src.open_router import OpenRouterChat
from src.agents.structured_outputs import ImageSelection, NewsClassifierReactions
#import datetime as dt
#import pytz


llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                     model_name=TEXT_GENERATION_MODEL)

text_image_llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                               model_name=TEXT_IMAGE_MODEL)

finalizer_llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                               model_name=TEXT_IMAGE_MODEL)

news_classifier_agent = relevance_prompt | llm | StrOutputParser() #.with_structured_output(NewsClassifierReactions) #| StrOutputParser()
rewriter_agent = rewiritter_prompt | llm | StrOutputParser()
search_query_gen_agent = theme_prompt | llm | StrOutputParser()

image_selection_agent = image_selection_prompt | text_image_llm.with_structured_output(ImageSelection)
image_description_agent = image_description_prompt | text_image_llm | StrOutputParser()

meme_agent = meme_find_prompt | text_image_llm | StrOutputParser()

final = final_prompt | finalizer_llm | StrOutputParser()

#ckpt = InMemorySaver()



@measure_time_async
async def classifier_node(state):
    post = state['post']
    emoji_reactions = state['emoji_reactions']
    grade = await news_classifier_agent.ainvoke({'post': post,
                                          'emoji_reactions':emoji_reactions})
    
    return {**state, 'grade': grade}


@measure_time_async
async def media_ctx_router(state):
    if state.get('media_links', []):
        return "🤡😂MemeNode"
    else:
        return "📄✍️RewriterNode"


@measure_time_async
async def meme_node(state):
    media_links = state.get('media_links', [])
    post = state['post']
    emoji_reactions = state.get('emoji_reactions', {})
    
    try:
        
        generation = await meme_agent.ainvoke({'image_url': media_links,
                                                'post':post,
                                                'reactions': f'Реакции с поста: {emoji_reactions}'})

        state['is_meme'] = is_meme = 'true' in generation.lower()
        if is_meme:
            state['generation'] = None
            
    except Exception as e:
        logger.info(f'Случилась какая - то при определении мемности поста: {e}')
        state['is_meme'] = False
    
    return state

@measure_time_async
async def meme_router(state):
    if not state['is_meme']:
        return "✈️🖼️MediaCtxNode"
    else:
        return END

@measure_time_async
async def media_ctx_node(state):

    if media_links:=state.get('media_links', []):
        try:
            image_description = await image_description_agent.ainvoke({'image_url': media_links})
            return {**state, 'media_ctx': image_description}
        
        except Exception as e:
            logger.info(f'Случилась какая - то ошибка описании картинки к посту {e}')
    
    return {**state, 'media_ctx': 'Нет изображения к посту'}


@measure_time_async
async def rewriter_node(state):
    post = state['post']
    grade = state['grade']
    media_ctx = state.get('media_ctx', '')
    generation = await rewriter_agent.ainvoke({'post': post,'grade':grade,
                                                'media_ctx': media_ctx})

    return {**state, 'generation': generation}


@measure_time_async
async def select_search_query_node(state):
    
    gen_post = state['generation']
    media_ctx = state.get('media_ctx', '')
    state['search_query']  = await search_query_gen_agent.ainvoke({'post': gen_post,
                                                                   'media_ctx': media_ctx})
    
    
    return state

@measure_time_async
async def select_image_to_post_node(state):
 
    search_query = state['search_query']
    generated_post = state['generation']
    
    finded_links = await asyncio.to_thread(get_ddgs_image_loads, query=search_query, max_images=5)
    rm_img_folders()

    if finded_links:        
        try:
            link_ind = await image_selection_agent.ainvoke({'query': "Какая картинка лучше всего подходит под следующий пост?"\
                                                                    f"Найдено всего: {len(finded_links)} изображений",
                                                     "post":generated_post,
                                                     "image_url": finded_links})
            link_ind = int(link_ind.image_number)
            
            if link_ind != -1:
                url = finded_links.pop(link_ind)
                return {**state, 'image_url': url}
            else:   
                return {**state, 'image_url': None}

        except Exception as e:
            logger.info(f'Случилась какая - то ошибка при выборе картинки к посту {e}')
    
    return {**state, 'image_url': None}

@measure_time_async
async def finalizer(state):
    state['generation'] = preproc_text_on_banned_org(state['generation'])
    state['generation'] = await final.ainvoke({"post": state['generation']})
    return state

    
workflow = StateGraph(SourceAgentGraph)
workflow.add_node('👀⁉️ClassifierReactionNode', classifier_node)
workflow.add_node('🤡😂MemeNode', meme_node)
workflow.add_node('✈️🖼️MediaCtxNode', media_ctx_node)
workflow.add_node('📄✍️RewriterNode', rewriter_node)
workflow.add_node("👀🕸️🌏MakeSearchQuery", select_search_query_node)
workflow.add_node('👀🖼️SelectImage4Post', select_image_to_post_node)
workflow.add_node('⁉️Finalizer', finalizer)

workflow.add_edge(START, '👀⁉️ClassifierReactionNode')
workflow.add_conditional_edges('👀⁉️ClassifierReactionNode',
                               media_ctx_router,
                               {"🤡😂MemeNode":"🤡😂MemeNode",
                                "📄✍️RewriterNode":"📄✍️RewriterNode"})

workflow.add_conditional_edges('🤡😂MemeNode',
                               meme_router,
                               {"✈️🖼️MediaCtxNode": "✈️🖼️MediaCtxNode",
                                END: END})

workflow.add_edge("✈️🖼️MediaCtxNode","📄✍️RewriterNode")
workflow.add_edge("📄✍️RewriterNode", "👀🕸️🌏MakeSearchQuery")

workflow.add_edge("👀🕸️🌏MakeSearchQuery", "👀🖼️SelectImage4Post")
workflow.add_edge("👀🖼️SelectImage4Post", "⁉️Finalizer")
workflow.add_edge("⁉️Finalizer", END)

async_graph = workflow.compile(debug=False)
