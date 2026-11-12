"""Keep the same pooled model without ONNX's additional packed weight copies."""

from fastembed import TextEmbedding
from fastembed.text.pooled_embedding import PooledEmbedding


class CompactPooledEmbedding(PooledEmbedding):
    @classmethod
    def add_extra_session_options(cls, options, extra):
        super().add_extra_session_options(options, extra)
        # Official ONNX session option: trade pre-packing speed for lower peak RAM.
        options.add_session_config_entry("session.disable_prepacking", "1")


class CompactTextEmbedding(TextEmbedding):
    EMBEDDINGS_REGISTRY = [
        CompactPooledEmbedding if model is PooledEmbedding else model
        for model in TextEmbedding.EMBEDDINGS_REGISTRY
    ]
