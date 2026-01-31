"""LangChain LLM client for TCM Knowledge Graph."""

from typing import Any, AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from tcm_kgraph.core.exceptions import LLMAPIError
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class LLMClient:
    """
    LLM client wrapper using LangChain.

    Provides a unified interface for interacting with OpenAI-compatible
    LLM APIs (DashScope, OpenAI, etc.)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "qwen-plus",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for the LLM service
            base_url: Base URL for the API
            model: Model name to use
            temperature: Generation temperature (0-2)
            max_tokens: Maximum tokens in response
        """
        self._model_name = model
        self._llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(f"LLM client initialized with model: {model}")

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._model_name

    def _convert_messages(
        self,
        messages: list[dict[str, str]],
    ) -> list[BaseMessage]:
        """Convert dict messages to LangChain message objects."""
        result: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            else:
                result.append(HumanMessage(content=content))

        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """
        Send chat messages and get response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters for the LLM

        Returns:
            Assistant response text

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            lc_messages = self._convert_messages(messages)
            response = await self._llm.ainvoke(lc_messages, **kwargs)
            return str(response.content)
        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            raise LLMAPIError(
                f"Chat completion failed: {e}",
                model=self._model_name,
                details={"messages_count": len(messages)},
            ) from e

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream chat response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters for the LLM

        Yields:
            Response text chunks

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            lc_messages = self._convert_messages(messages)
            async for chunk in self._llm.astream(lc_messages, **kwargs):
                if chunk.content:
                    yield str(chunk.content)
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            raise LLMAPIError(
                f"Stream completion failed: {e}",
                model=self._model_name,
            ) from e

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages, **kwargs)

    async def generate_with_template(
        self,
        template: str,
        variables: dict[str, Any],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text using a prompt template.

        Args:
            template: Prompt template with {variable} placeholders
            variables: Dictionary of template variables
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt or "You are a helpful assistant."),
            ("user", template),
        ])

        formatted = prompt_template.format_messages(**variables)
        response = await self._llm.ainvoke(formatted, **kwargs)
        return str(response.content)

    async def extract_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate and parse JSON response.

        Args:
            prompt: Prompt requesting JSON output
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON as dictionary

        Raises:
            LLMAPIError: If JSON parsing fails
        """
        import json

        system = system_prompt or (
            "You are a helpful assistant that outputs valid JSON. "
            "Always respond with properly formatted JSON only, no other text."
        )

        response = await self.generate(prompt, system_prompt=system)

        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()

            return json.loads(response)
        except json.JSONDecodeError as e:
            raise LLMAPIError(
                f"Failed to parse JSON response: {e}",
                model=self._model_name,
                details={"response": response[:500]},
            ) from e
