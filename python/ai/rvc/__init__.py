"""
RVC (Retrieval-based Voice Conversion) inference package.

Supports CPU, CUDA (NVIDIA), and DirectML (AMD/Intel GPU) inference.

This package provides:
- Voice conversion pipeline (HuBERT + RMVPE + VITS synthesizer)
- Device detection (CPU / CUDA / DirectML)
- Real-time mic voice conversion (mic_rvc)
- FAISS index retrieval (optional, graceful degradation)
"""

__version__ = "1.0.0"
__all__ = ["config", "pipeline", "rmvpe", "audio", "mic_rvc"]
