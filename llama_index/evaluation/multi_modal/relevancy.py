"""Relevancy evaluation."""
from __future__ import annotations

from typing import Any, List, Sequence

from llama_index import SimpleDirectoryReader
from llama_index.evaluation.base import BaseEvaluator, EvaluationResult
from llama_index.multi_modal_llms.base import MultiModalLLM
from llama_index.multi_modal_llms.openai import OpenAIMultiModal
from llama_index.node_parser import SimpleNodeParser
from llama_index.prompts import BasePromptTemplate, PromptTemplate
from llama_index.prompts.mixin import PromptDictType

DEFAULT_EVAL_TEMPLATE = PromptTemplate(
    "Your task is to evaluate if the response for the query \
    is in line with the images and textual context information provided.\n"
    "You have two options to answer. Either YES/ NO.\n"
    "Answer - YES, if the response for the query \
    is in line with context information otherwise NO.\n"
    "Query and Response: \n {query_str}\n"
    "Context: \n {context_str}\n"
    "Answer: "
)

DEFAULT_REFINE_TEMPLATE = PromptTemplate(
    "We want to understand if the following query and response is"
    "in line with the context information: \n {query_str}\n"
    "We have provided an existing YES/NO answer: \n {existing_answer}\n"
    "We have the opportunity to refine the existing answer "
    "(only if needed) with some more context below.\n"
    "------------\n"
    "{context_msg}\n"
    "------------\n"
    "If the existing answer was already YES, still answer YES. "
    "If the information is present in the new context, answer YES. "
    "Otherwise answer NO.\n"
)


class MultiModalRelevancyEvaluator(BaseEvaluator):
    """Relenvancy evaluator.

    Evaluates the relevancy of retrieved image and textual contexts and response to a query.
    This evaluator considers the query string, retrieved contexts, and response string.

    Args:
        service_context(Optional[ServiceContext]):
            The service context to use for evaluation.
        raise_error(Optional[bool]):
            Whether to raise an error if the response is invalid.
            Defaults to False.
        eval_template(Optional[Union[str, BasePromptTemplate]]):
            The template to use for evaluation.
        refine_template(Optional[Union[str, BasePromptTemplate]]):
            The template to use for refinement.
    """

    def __init__(
        self,
        multi_modal_llm: MultiModalLLM | None = None,
        raise_error: bool = False,
        eval_template: str | BasePromptTemplate | None = None,
        refine_template: str | BasePromptTemplate | None = None,
    ) -> None:
        """Init params."""
        self._multi_modal_llm = multi_modal_llm or OpenAIMultiModal(
            model="gpt-4-vision-preview", max_new_tokens=1000
        )
        self._raise_error = raise_error

        self._eval_template: BasePromptTemplate
        if isinstance(eval_template, str):
            self._eval_template = PromptTemplate(eval_template)
        else:
            self._eval_template = eval_template or DEFAULT_EVAL_TEMPLATE

        self._refine_template: BasePromptTemplate
        if isinstance(refine_template, str):
            self._refine_template = PromptTemplate(refine_template)
        else:
            self._refine_template = refine_template or DEFAULT_REFINE_TEMPLATE

    def _get_prompts(self) -> PromptDictType:
        """Get prompts."""
        return {
            "eval_template": self._eval_template,
            "refine_template": self._refine_template,
        }

    def _update_prompts(self, prompts: PromptDictType) -> None:
        """Update prompts."""
        if "eval_template" in prompts:
            self._eval_template = prompts["eval_template"]
        if "refine_template" in prompts:
            self._refine_template = prompts["refine_template"]

    def evaluate(
        self,
        query: str | None = None,
        response: str | None = None,
        contexts: Sequence[str] | None = None,
        image_paths: List[str] | None = None,
        image_urls: List[str] | None = None,
        **kwargs: Any,
    ) -> EvaluationResult:
        """Evaluate whether the contexts and response are relevant to the query."""
        del kwargs  # Unused

        if query is None or contexts is None or response is None:
            raise ValueError("query, contexts, and response must be provided")

        context_str = "\n\n".join(contexts)
        evaluation_query_str = f"Question: {query}\nResponse: {response}"
        fmt_prompt = self._eval_template.format(
            context_str=context_str, query_str=evaluation_query_str
        )

        image_documents = []
        if image_paths:
            for image_path in image_paths:
                image_documents += SimpleDirectoryReader(
                    input_files=[image_path]
                ).load_data()
            node_parser = SimpleNodeParser.from_defaults()
            image_nodes = node_parser.get_nodes_from_documents(image_documents)

        response_obj = self._multi_modal_llm.complete(
            prompt=fmt_prompt,
            image_documents=image_nodes,
        )

        raw_response_txt = str(response_obj)

        if "yes" in raw_response_txt.lower():
            passing = True
        else:
            if self._raise_error:
                raise ValueError("The response is invalid")
            passing = False

        return EvaluationResult(
            query=query,
            response=response,
            passing=passing,
            score=1.0 if passing else 0.0,
            feedback=raw_response_txt,
        )

    async def aevaluate(
        self,
        query: str | None = None,
        response: str | None = None,
        contexts: Sequence[str] | None = None,
        image_paths: List[str] | None = None,
        image_urls: List[str] | None = None,
        **kwargs: Any,
    ) -> EvaluationResult:
        """Async evaluate whether the contexts and response are relevant to the query."""
        del kwargs  # Unused

        if query is None or contexts is None or response is None:
            raise ValueError("query, contexts, and response must be provided")

        context_str = "\n\n".join(contexts)
        evaluation_query_str = f"Question: {query}\nResponse: {response}"
        fmt_prompt = self._eval_template.format(
            context_str=context_str, query_str=evaluation_query_str
        )

        image_documents = []
        if image_paths:
            for image_path in image_paths:
                image_documents += SimpleDirectoryReader(
                    input_files=[image_path]
                ).load_data()
            node_parser = SimpleNodeParser.from_defaults()
            image_nodes = node_parser.get_nodes_from_documents(image_documents)

        response_obj = await self._multi_modal_llm.acomplete(
            prompt=fmt_prompt,
            image_documents=image_nodes,
        )

        raw_response_txt = str(response_obj)

        if "yes" in raw_response_txt.lower():
            passing = True
        else:
            if self._raise_error:
                raise ValueError("The response is invalid")
            passing = False

        return EvaluationResult(
            query=query,
            response=response,
            passing=passing,
            score=1.0 if passing else 0.0,
            feedback=raw_response_txt,
        )
