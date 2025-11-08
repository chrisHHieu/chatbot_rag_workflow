from typing import Dict, TypedDict
from langgraph.graph import MessagesState
from langmem.short_term import RunningSummary


class State(MessagesState):
    """State với memory context cho LangGraph."""
    context: Dict[str, RunningSummary]

