#!/usr/bin/env python3
"""
LangSmith Evaluation Script for Hybrid RAG (llmops_rag)

This script runs evaluations on the Hybrid RAG system using
- A lightweight RAG answer function built on DocumentIngestor + ModelLoader
- A custom correctness evaluator (LLM-as-a-Judge via OpenAI)
- Optional LangSmith integration if environment variables are present

Usage:
    python run_evaluations.py --dataset MyDataset
    python run_evaluations.py --dataset MyDataset --evaluator correctness
    python run_evaluations.py --dataset MyDataset --evaluator all
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

# Optional LangSmith imports (guarded)
try:
    from langsmith import Client  # noqa: F401
    from langsmith.schemas import Run, Example  # type: ignore
    from langsmith.evaluation import evaluate, LangChainStringEvaluator  # type: ignore
    HAS_LANGSMITH = True
except Exception:
    HAS_LANGSMITH = False
    Run = object  # type: ignore
    Example = object  # type: ignore

from langchain_core.prompts import ChatPromptTemplate
from multi_doc_chat.src.document_ingestion.data_ingestion import DocumentIngestor
from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.prompts.prompt_library import ANSWER_PROMPT
from multi_doc_chat.logger import GLOBAL_LOGGER as log


# ============================================================================
# Simple RAG Answer Function (no graph, no streaming)
# ============================================================================

def rag_answer(
    inputs: dict,
    pdf_path: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    k: int = 5,
) -> dict:
    """
    Answer a question against a single PDF using Hybrid RAG.

    Args:
        inputs: {"question": "..."}
        pdf_path: Path to PDF file (defaults to OOS_Nội quy lao động_2025_Final.pdf in repo root)
        chunk_size: Text chunk size
        chunk_overlap: Chunk overlap
        k: Number of documents to retrieve (applied to vector side; bm25_k comes from config)

    Returns:
        {"answer": "..."}
    """
    try:
        question = (inputs or {}).get("question", "").strip()
        if not question:
            return {"answer": "No question provided"}

        # Default to example PDF in repo root
        if not pdf_path:
            default_pdf = PROJECT_ROOT / "OOS_Nội quy lao động_2025_Final.pdf"
            pdf_path = str(default_pdf)

        if not Path(pdf_path).exists():
            return {"answer": f"Data file not found: {pdf_path}"}

        # 1) Ingest
        ingestor = DocumentIngestor()
        docs = ingestor.load_documents(pdf_path)
        doc_splits = ingestor.split_documents(docs)

        # 2) Build hybrid retriever
        hybrid_retriever = ingestor.create_hybrid_retriever(doc_splits)

        # 3) Retrieve relevant docs
        # EnsembleRetriever (langchain_classic) behaves as a Runnable; use .invoke
        retrieved_docs = hybrid_retriever.invoke(question)

        # 4) Format context and ask LLM using ANSWER_PROMPT
        context_texts: List[str] = []
        for d in retrieved_docs[:max(1, k)]:
            try:
                context_texts.append(getattr(d, "page_content", str(d)))
            except Exception:
                continue
        context = "\n\n".join(context_texts) if context_texts else ""

        ml = ModelLoader()
        llm = ml.load_response_model()

        prompt = ChatPromptTemplate.from_messages([
            ("system", ANSWER_PROMPT),
            ("human", "{question}")
        ])
        chain = prompt | llm
        response = chain.invoke({"question": question, "context": context})

        # Handle different return structures
        answer = getattr(response, "content", None) or str(response)
        return {"answer": answer}

    except Exception as e:
        log.error("rag_answer failed", error=str(e))
        return {"answer": f"Error: {str(e)}"}


# ============================================================================
# Custom Correctness Evaluator (LLM-as-a-Judge via OpenAI)
# ============================================================================

def correctness_evaluator(run: Run, example: Example) -> dict:  # type: ignore[override]
    """
    Judge correctness by comparing actual vs expected answers via an LLM.
    Uses the same provider stack (OpenAI) via ModelLoader for consistency.
    """
    try:
        actual_output = (getattr(run, "outputs", None) or {}).get("answer", "")
        expected_output = (getattr(example, "outputs", None) or {}).get("answer", "")
        input_question = (getattr(example, "inputs", None) or {}).get("question", "")

        eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an evaluator whose job is to judge correctness.\n\n"
                       "Correctness means how well the actual model output matches the reference output in terms of"
                       " factual accuracy, coverage, and meaning.\n\n"
                       "- If the actual output matches the reference output semantically, mark CORRECT.\n"
                       "- If it misses key facts or is factually incorrect, mark INCORRECT.\n\n"
                       "Respond with two lines:\n"
                       "Reasoning: <your short reasoning>\n"
                       "Verdict: <CORRECT or INCORRECT>"""),
            ("human", """<example>\n<input>\n{input}\n</input>\n\n<output>\nExpected Output: {expected_output}\n\nActual Output: {actual_output}\n</output>\n</example>""")
        ])

        ml = ModelLoader()
        judge_llm = ml.load_grader_model()
        chain = eval_prompt | judge_llm
        resp = chain.invoke({
            "input": input_question,
            "expected_output": expected_output,
            "actual_output": actual_output,
        })
        text = getattr(resp, "content", "")

        reasoning, verdict = "", ""
        for line in text.split("\n"):
            if line.startswith("Reasoning:"):
                reasoning = line.replace("Reasoning:", "").strip()
            elif line.startswith("Verdict:"):
                verdict = line.replace("Verdict:", "").strip()

        score = 1 if "CORRECT" in verdict.upper() else 0
        return {"key": "correctness", "score": score, "reasoning": reasoning, "comment": f"Verdict: {verdict}"}

    except Exception as e:
        return {"key": "correctness", "score": 0, "reasoning": f"Error during evaluation: {str(e)}"}


# ============================================================================
# Main Evaluation Function
# ============================================================================

def run_evaluation(
    dataset_name: str = "rag_chatbot_humax",
    evaluator_type: str = "correctness",
    experiment_prefix: Optional[str] = None,
    description: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    k: int = 5,
):
    """
    Run evaluation on the Hybrid RAG system.

    Args:
        dataset_name: Name of the dataset in LangSmith
        evaluator_type: 'correctness', 'cot_qa', or 'all'
        experiment_prefix: Prefix for the experiment name
        description: Description for the experiment
        chunk_size: Chunk size for document splitting
        chunk_overlap: Overlap between chunks
        k: Number of documents to retrieve
    """
    print(f"\n{'='*80}")
    print(f"Running Evaluation on Dataset: {dataset_name}")
    print(f"Evaluator Type: {evaluator_type}")
    print(f"{'='*80}\n")

    if not HAS_LANGSMITH:
        print("Warning: LangSmith is not installed or not configured. Running a single local check only.\n")
        # Run a single local check for demonstration
        out = rag_answer({"question": "What is the working time policy?"}, k=k)
        print("Local check output:", out)
        return None

    # Select evaluators based on type
    evaluators = []
    if evaluator_type == "correctness":
        evaluators = [correctness_evaluator]
        exp_prefix = experiment_prefix or "hybridRAG-correctness"
        desc = description or "Evaluating Hybrid RAG with custom correctness evaluator"
    elif evaluator_type == "cot_qa":
        evaluators = [LangChainStringEvaluator("cot_qa")]
        exp_prefix = experiment_prefix or "hybridRAG-cot-qa"
        desc = description or "Evaluating Hybrid RAG with Chain-of-Thought QA evaluator"
    elif evaluator_type == "all":
        evaluators = [correctness_evaluator, LangChainStringEvaluator("cot_qa")]
        exp_prefix = experiment_prefix or "hybridRAG-multi-eval"
        desc = description or "Evaluating Hybrid RAG with multiple evaluators (correctness + cot_qa)"
    else:
        print(f"Error: Unknown evaluator type '{evaluator_type}'")
        print("Available types: correctness, cot_qa, all")
        return None

    metadata = {
        "variant": "Hybrid RAG (FAISS + BM25)",
        "evaluator_type": evaluator_type,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "k": k,
    }

    print("Starting evaluation...")

    try:
        experiment_results = evaluate(
            rag_answer,
            data=dataset_name,
            evaluators=evaluators,
            experiment_prefix=exp_prefix,
            description=desc,
            metadata=metadata,
        )

        print("\n" + "="*80)
        print("Evaluation Completed Successfully!")
        print("="*80)

        if hasattr(experiment_results, 'experiment_name'):
            print(f"\nExperiment Name: {experiment_results.experiment_name}")

        print("\nCheck the LangSmith UI for detailed results:")
        print("https://smith.langchain.com/")

        return experiment_results

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"Error during evaluation: {str(e)}")
        print(f"{'='*80}\n")
        raise


# ============================================================================
# Command Line Interface
# ============================================================================

def main():
    """Main function to run evaluations from command line."""
    global HAS_LANGSMITH  # ✅ THÊM DÒNG NÀY Ở ĐÂY
    parser = argparse.ArgumentParser(
        description="Run LangSmith evaluations on the Hybrid RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with correctness evaluator
  python run_evaluations.py --dataset MyDataset --evaluator correctness
  
  # Run with chain-of-thought QA evaluator
  python run_evaluations.py --dataset MyDataset --evaluator cot_qa
  
  # Run with all evaluators
  python run_evaluations.py --dataset MyDataset --evaluator all
  
  # Run with custom parameters
  python run_evaluations.py --dataset MyDataset --evaluator correctness --chunk-size 500 --k 10
        """
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default="MyDataset",
        help="Name of the dataset in LangSmith (default: MyDataset)"
    )

    parser.add_argument(
        "--evaluator",
        type=str,
        choices=["correctness", "cot_qa", "all"],
        default="correctness",
        help="Type of evaluator to use (default: correctness)"
    )

    parser.add_argument(
        "--experiment-prefix",
        type=str,
        default=None,
        help="Custom prefix for experiment name"
    )

    parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="Custom description for the experiment"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for document splitting (default: 1000)"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Overlap between chunks (default: 200)"
    )

    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of documents to retrieve (default: 5)"
    )

    args = parser.parse_args()

    # Check for LangSmith env if using LangSmith path
    if HAS_LANGSMITH:
        required_env_vars = ["LANGSMITH_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            print(f"\nWarning: Missing environment variables for LangSmith: {', '.join(missing_vars)}")
            print("Falling back to local check.\n")
            HAS_LANGSMITH = False

    # Run evaluation
    try:
        run_evaluation(
            dataset_name=args.dataset,
            evaluator_type=args.evaluator,
            experiment_prefix=args.experiment_prefix,
            description=args.description,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            k=args.k
        )
    except KeyboardInterrupt:
        print("\n\nEvaluation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
