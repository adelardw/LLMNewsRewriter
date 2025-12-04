from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import START, END, StateGraph
from loguru import logger
import asyncio
from datetime import datetime
from src.config import OPEN_ROUTER_API_KEY, TEXT_IMAGE_MODEL, TEXT_GENERATION_MODEL, FINALIZER_LLM


from src.agents.prompts import (rewiritter_prompt, relevance_prompt, image_selection_prompt,theme_prompt,
                                image_description_prompt, meme_find_prompt,final_prompt, filter_prompt)

from src.agents.agent_schemas import SourceAgentGraph
from src.agents.utils import preproc_text_on_banned_org, measure_time_async
from src.tools.google_web_search import get_ddgs_image_loads
from src.tools.utils import rm_img_folders
from src.open_router import OpenRouterChat
from src.agents.structured_outputs import ImageSelection, FilterOutput

logger.add("logger_result.log", format="{time} {level} {message}", level="INFO")

llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                     model_name=TEXT_GENERATION_MODEL)

text_image_llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                               model_name=TEXT_IMAGE_MODEL)

finalizer_llm = OpenRouterChat(api_key=OPEN_ROUTER_API_KEY,
                               model_name=FINALIZER_LLM)


filter_agent = filter_prompt | llm.with_structured_output(FilterOutput)

news_classifier_agent = relevance_prompt | llm | StrOutputParser()
rewriter_agent = rewiritter_prompt | llm | StrOutputParser()
search_query_gen_agent = theme_prompt | llm.bind(max_tokens=40) | StrOutputParser()

image_selection_agent = image_selection_prompt | text_image_llm.with_structured_output(ImageSelection)
image_description_agent = image_description_prompt | text_image_llm | StrOutputParser()

meme_agent = meme_find_prompt | text_image_llm | StrOutputParser()

final = final_prompt | finalizer_llm | StrOutputParser()


'''@measure_time_async
async def prefilter_node(state):
    is_not_shit = await filter_agent.ainvoke({"post": state['post']})
    state['good_news'] = is_not_shit.good_news
    logger.info(f'[FILTERRESULT TAG] | Good News: {is_not_shit}')
    return state

@measure_time_async
async def prefilter_router(state):
    if state['good_news']:
        return "👀⁉️ClassifierReactionNode"
    else:
        return END'''
    
@measure_time_async
async def classifier_node(state):
    post = state['post']
    emoji_reactions = state['emoji_reactions']
    if emoji_reactions:
        state['grade'] = await news_classifier_agent.ainvoke({'post': post,
                                                             'emoji_reactions':emoji_reactions})
    return state


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
    
    return state


@measure_time_async
async def rewriter_node(state):
    post = state['post']
    grade = state.get('grade', None)
    media_ctx = state.get('media_ctx', None)
    
    if grade or media_ctx:
        addititional_info = "\n Дополнительная информация к посту: \n"\
        
        addititional_info +=  f"Аггрегированная оценка от агента: \n {grade} \n" if grade else ''
        addititional_info += f"Описание изображения к посту (ТОЛЬКО КАК КОНТЕКСТ): \n {media_ctx} \n" if media_ctx else ''
                       
        post += addititional_info

    
    state['generation'] = await rewriter_agent.ainvoke({'post': post})


    return state

@measure_time_async
async def postfilter_node(state):
    is_not_shit = await filter_agent.ainvoke({"post": state['generation']})
    state['good_news'] = is_not_shit.good_news
    state['generation'] = state['generation'] if state['good_news'] else None
    logger.info(f'[GOODGEN TAG] | {state["good_news"]}')
    return state

@measure_time_async
async def postfilter_router(state):
    if state['good_news']:
        return "👀🕸️🌏MakeSearchQuery"
    else:
        return END

@measure_time_async
async def select_search_query_node(state):
    
    gen_post = state['generation']
    media_ctx = state.get('media_ctx', '')
    date = datetime.now()
    
    month = date.month
    year = date.year
    
    state['search_query']  = await search_query_gen_agent.ainvoke({'post': gen_post,
                                                                   'date': f'\n Cейчас: {month} месяц и {year} год',
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
            link_ind = await image_selection_agent.ainvoke({'query': "Какое изображение / фотография / картинка лучше всего подходит под следующий пост? \n "\
                                                                    f"Текст поста: \n {generated_post} \n" \
                                                                    f"Найдено всего: {len(finded_links)} изображений",

                                                            'image_url': finded_links})
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
    text = preproc_text_on_banned_org(state['generation'])
    generation = await final.ainvoke({"post": text})
    validation = await filter_agent.ainvoke({"post": generation})
    state['generation'] = generation if validation.good_news else None
    logger.critical(f"[FINALGENERATED TAG] | {state['generation']}")
    return state

    
workflow = StateGraph(SourceAgentGraph)
#workflow.add_node('📄⁉️PreFilterNode', prefilter_node)
workflow.add_node('👀⁉️ClassifierReactionNode', classifier_node)
workflow.add_node('🤡😂MemeNode', meme_node)
workflow.add_node('✈️🖼️MediaCtxNode', media_ctx_node)
workflow.add_node('📄✍️RewriterNode', rewriter_node)
workflow.add_node('✍️⁉️PostFilterNode', postfilter_node)
workflow.add_node("👀🕸️🌏MakeSearchQuery", select_search_query_node)
workflow.add_node('👀🖼️SelectImage4Post', select_image_to_post_node)
workflow.add_node('⁉️Finalizer', finalizer)


# workflow.add_edge(START, '📄⁉️PreFilterNode')
# workflow.add_conditional_edges('📄⁉️PreFilterNode',
#                                prefilter_router,
#                                {"👀⁉️ClassifierReactionNode":"👀⁉️ClassifierReactionNode",
#                                 END:END})

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
#workflow.add_edge("📄✍️RewriterNode", "👀🕸️🌏MakeSearchQuery")
workflow.add_edge("📄✍️RewriterNode", "✍️⁉️PostFilterNode")

workflow.add_conditional_edges('✍️⁉️PostFilterNode',
                               postfilter_router,
                               {"👀🕸️🌏MakeSearchQuery":"👀🕸️🌏MakeSearchQuery",
                                END:END})

workflow.add_edge("👀🕸️🌏MakeSearchQuery", "👀🖼️SelectImage4Post")
workflow.add_edge("👀🖼️SelectImage4Post", "⁉️Finalizer")
workflow.add_edge("⁉️Finalizer", END)

async_graph = workflow.compile(debug=False)
