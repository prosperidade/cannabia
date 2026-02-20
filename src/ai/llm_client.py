import json
import logging
from typing import Any, Type

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class LLMClient:

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0):
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
        )

    def run_structured_prompt(
        self,
        prompt_template: str,
        schema_model: Type,
        **kwargs
    ) -> Any:

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm

        response = chain.invoke(kwargs)
        raw_output = response.content.strip()

        logger.info("LLM raw output: %s", raw_output)

        try:
            parsed_json = json.loads(raw_output)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON returned by LLM")
            raise ValueError("LLM retornou JSON inválido") from e

        try:
            validated = schema_model(**parsed_json)
        except ValidationError as e:
            logger.error("Schema validation error: %s", str(e))
            raise ValueError("Resposta não corresponde ao schema esperado") from e

        return validated
