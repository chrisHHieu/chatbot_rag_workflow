from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately
from multi_doc_chat.model.models import State
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logger import GLOBAL_LOGGER as log


class GraphBuilder:
    """Builds and configures the LangGraph workflow."""
    
    def __init__(
        self, 
        retriever_tool, 
        graph_nodes,
        model_loader: Optional[ModelLoader] = None,
        config: Optional[dict] = None
    ):
        """
        Initialize GraphBuilder.
        
        Args:
            retriever_tool: Retriever tool for document search
            graph_nodes: GraphNodes instance
            model_loader: Optional shared ModelLoader instance
            config: Optional config dict
        """
        self.config = config or load_config()
        self.model_loader = model_loader or ModelLoader(config=self.config)
        self.retriever_tool = retriever_tool
        self.graph_nodes = graph_nodes
        log.info("GraphBuilder initialized")
    
    def _create_summarization_node(self):
        """Create summarization node for conversation memory."""
        try:
            summarization_config = self.config["summarization"]
            
            grader_model = self.model_loader.load_grader_model()
            summarization_model = grader_model.bind(
                max_tokens=summarization_config.get("max_tokens", 15000),  # ✅ Optimized for 1M context window
                temperature=summarization_config.get("temperature", 0.1)
            )
            
            summarization_node = SummarizationNode(
                token_counter=count_tokens_approximately,
                model=summarization_model,
                max_tokens=summarization_config.get("max_tokens_total", 75000),  # ✅ 90% of 1M context window
                max_tokens_before_summary=summarization_config.get("max_tokens_before_summary", 200000),  # ✅ Trigger at 70%
                max_summary_tokens=summarization_config.get("max_summary_tokens", 15000),  # ✅ Detailed summaries
            )
            
            log.info("Summarization node created")
            return summarization_node
            
        except Exception as e:
            log.error("Failed creating summarization node", error=str(e))
            raise
    
    def build_graph(self):
        """Build the complete LangGraph workflow."""
        try:
            workflow = StateGraph(State)
            
            # Create summarization node
            summarization_node = self._create_summarization_node()
            
            # Add nodes
            workflow.add_node("summarize", summarization_node)
            workflow.add_node("generate_query_or_respond", self.graph_nodes.generate_query_or_respond)
            workflow.add_node("generate_answer", self.graph_nodes.generate_answer)
            workflow.add_node("retrieve", ToolNode([self.retriever_tool]))
            
            # Build flow
            workflow.add_edge(START, "summarize")
            workflow.add_edge("summarize", "generate_query_or_respond")
            
            # Conditional: model quyết định có cần retrieve không
            workflow.add_conditional_edges(
                "generate_query_or_respond",
                tools_condition,
                {
                    "tools": "retrieve",      # Nếu model gọi tool → retrieve
                    END: END,                  # Nếu model trả lời trực tiếp → END
                },
            )
            
            # Sau khi retrieve → luôn generate answer
            workflow.add_edge("retrieve", "generate_answer")
            workflow.add_edge("generate_answer", END)
            
            log.info("Graph workflow built successfully")
            return workflow
            
        except Exception as e:
            log.error("Failed building graph", error=str(e))
            raise

