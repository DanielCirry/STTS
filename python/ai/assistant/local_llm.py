"""
Local LLM Provider using llama-cpp-python
Runs local GGUF models for offline AI assistant
"""

import logging
from pathlib import Path
from typing import Optional

from ai.assistant.base import AIProvider, AssistantResponse, AssistantConfig, truncate_response

logger = logging.getLogger('stts.assistant.local')


# Recommended local models for VRChat companion use
RECOMMENDED_MODELS = {
    'llama-3.2-1B-Instruct': {
        'url': 'https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF',
        'filename': 'Llama-3.2-1B-Instruct-Q4_K_M.gguf',
        'size': '~0.8 GB',
        'description': 'Fast, good for simple queries'
    },
    'llama-3.2-3B-Instruct': {
        'url': 'https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF',
        'filename': 'Llama-3.2-3B-Instruct-Q4_K_M.gguf',
        'size': '~2 GB',
        'description': 'Balanced speed and quality'
    },
    'Phi-3-mini-4k-instruct': {
        'url': 'https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf',
        'filename': 'Phi-3-mini-4k-instruct-q4.gguf',
        'size': '~2.3 GB',
        'description': 'Microsoft Phi-3, excellent reasoning'
    },
}


class LocalLLMProvider(AIProvider):
    """Local LLM provider using llama-cpp-python."""

    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize local LLM provider.

        Args:
            models_dir: Directory containing GGUF models
        """
        super().__init__()
        self.name = "local"
        self.is_online = False

        # Model paths
        if models_dir is None:
            import os
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            models_dir = Path(appdata) / 'STTS' / 'models' / 'llm'

        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)

        # LLM instance
        self._llm = None
        self._current_model: Optional[str] = None
        self._n_ctx = 2048
        self._n_gpu_layers = -1  # Auto-detect, use all GPU layers

    def load_model(self, model_path: str, n_ctx: int = 2048, n_gpu_layers: int = -1) -> bool:
        """Load a GGUF model.

        Args:
            model_path: Path to GGUF file or model name
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 for auto)

        Returns:
            True if loaded successfully
        """
        try:
            from llama_cpp import Llama

            # Resolve model path
            if not Path(model_path).is_absolute():
                model_path = str(self._models_dir / model_path)

            if not Path(model_path).exists():
                logger.error(f"Model not found: {model_path}")
                return False

            logger.info(f"Loading local LLM: {model_path}")

            self._llm = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )

            self._current_model = Path(model_path).name
            self._n_ctx = n_ctx
            self._n_gpu_layers = n_gpu_layers
            self.is_loaded = True

            logger.info(f"Local LLM loaded: {self._current_model}")
            return True

        except ImportError:
            logger.error("llama-cpp-python not installed")
            return False
        except Exception as e:
            logger.error(f"Error loading local LLM: {e}")
            return False

    def unload_model(self):
        """Unload the current model."""
        self._llm = None
        self._current_model = None
        self.is_loaded = False
        logger.info("Local LLM unloaded")

    async def generate(self, prompt: str) -> AssistantResponse:
        """Generate a response using the local LLM.

        Args:
            prompt: User input

        Returns:
            AssistantResponse with the generated content
        """
        if not self._llm:
            raise RuntimeError("Model not loaded")

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build messages for chat completion
            messages = [{'role': 'system', 'content': self._config.system_prompt}]
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            # Generate response
            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                stop=['<|eot_id|>', '<|end|>', '</s>']
            )

            content = response['choices'][0]['message']['content'].strip()
            tokens_used = response.get('usage', {}).get('total_tokens', 0)

            # Truncate for VRChat
            content, truncated = truncate_response(content, self._config.max_response_length)

            # Add assistant response to conversation
            self.add_message('assistant', content)

            return AssistantResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._current_model,
                truncated=truncated
            )

        except Exception as e:
            logger.error(f"Local LLM generation error: {e}")
            raise

    async def generate_stream(self, prompt: str):
        """Generate a streaming response.

        Args:
            prompt: User input

        Yields:
            Token strings as they are generated
        """
        if not self._llm:
            raise RuntimeError("Model not loaded")

        # Add user message to conversation
        self.add_message('user', prompt)

        try:
            # Build messages for chat completion
            messages = [{'role': 'system', 'content': self._config.system_prompt}]
            for msg in self._conversation:
                messages.append({'role': msg.role, 'content': msg.content})

            # Generate response with streaming
            full_response = ""
            for chunk in self._llm.create_chat_completion(
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                stop=['<|eot_id|>', '<|end|>', '</s>'],
                stream=True
            ):
                delta = chunk['choices'][0].get('delta', {})
                if 'content' in delta:
                    token = delta['content']
                    full_response += token
                    if self._on_token:
                        self._on_token(token)
                    yield token

            # Add assistant response to conversation
            self.add_message('assistant', full_response.strip())

        except Exception as e:
            logger.error(f"Local LLM streaming error: {e}")
            raise

    def is_available(self) -> bool:
        """Check if llama-cpp-python is available."""
        try:
            from llama_cpp import Llama
            return True
        except ImportError:
            return False

    def get_available_models(self) -> list:
        """Get list of available/downloaded models.

        Returns:
            List of model info dicts
        """
        models = []

        # Check for downloaded models
        if self._models_dir.exists():
            for model_file in self._models_dir.glob('*.gguf'):
                models.append({
                    'name': model_file.stem,
                    'path': str(model_file),
                    'size': model_file.stat().st_size,
                    'downloaded': True
                })

        # Add recommended models that aren't downloaded
        for name, info in RECOMMENDED_MODELS.items():
            if not any(m['name'] == name for m in models):
                models.append({
                    'name': name,
                    'url': info['url'],
                    'filename': info['filename'],
                    'size': info['size'],
                    'description': info['description'],
                    'downloaded': False
                })

        return models

    @property
    def current_model(self) -> Optional[str]:
        """Get the name of the currently loaded model."""
        return self._current_model

    def set_models_directory(self, path: str) -> bool:
        """Set the models directory.

        Args:
            path: Path to the models directory

        Returns:
            True if directory exists or was created
        """
        try:
            models_dir = Path(path)
            models_dir.mkdir(parents=True, exist_ok=True)
            self._models_dir = models_dir
            logger.debug(f"Models directory set to: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set models directory: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        self.unload_model()
