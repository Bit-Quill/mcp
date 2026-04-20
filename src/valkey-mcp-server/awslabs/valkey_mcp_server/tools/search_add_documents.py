# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Document ingestion tool for Valkey Search."""

import json
import logging
from awslabs.valkey_mcp_server.common.connection import ValkeyConnectionManager
from awslabs.valkey_mcp_server.common.server import mcp
from awslabs.valkey_mcp_server.common.utils import pack_embedding
from awslabs.valkey_mcp_server.context import Context
from awslabs.valkey_mcp_server.embeddings import create_embeddings_provider
from typing import Any, Dict, List, Optional
from valkey.exceptions import ValkeyError


_embeddings_provider = None


def _acquire_embeddings_provider():
    global _embeddings_provider
    if _embeddings_provider is None:
        _embeddings_provider = create_embeddings_provider()
    return _embeddings_provider


def _index_exists(r, index_name: str) -> bool:
    try:
        r.execute_command('FT.INFO', index_name)
        return True
    except ValkeyError:
        return False


def _auto_create_index(
    r,
    index_name: str,
    prefix: str,
    embedding_field: str,
    dimensions: int,
):
    """Create a minimal vector index for auto-creation."""
    cmd: list = [
        'FT.CREATE',
        index_name,
        'ON',
        'HASH',
        'PREFIX',
        '1',
        prefix,
        'SCHEMA',
        embedding_field,
        'VECTOR',
        'HNSW',
        '6',
        'TYPE',
        'FLOAT32',
        'DIM',
        str(dimensions),
        'DISTANCE_METRIC',
        'COSINE',
    ]
    r.execute_command(*cmd)


@mcp.tool()
async def add_documents(
    index_name: str,
    documents: List[Dict[str, Any]],
    id_field: str = 'id',
    prefix: Optional[str] = None,
    embedding_field: Optional[str] = None,
    text_fields: Optional[List[str]] = None,
    embedding_dimensions: Optional[int] = None,
) -> Dict[str, Any]:
    """Add documents to a Valkey Search index with optional embedding generation.

    Stores documents as Valkey hashes. When embedding_field and text_fields are
    provided, generates vector embeddings via the configured provider (Bedrock,
    OpenAI, or Ollama), binary-packs them, and stores alongside document data.
    Auto-creates the index if it doesn't exist and embeddings are generated.

    Args:
        index_name: Name of the Valkey Search index
        documents: List of dicts, each must contain a field matching id_field
        id_field: Field to use as document ID (default: "id")
        prefix: Key prefix (e.g., "docs:"). Defaults to "{index_name}:"
        embedding_field: Vector field name. None = no embeddings generated.
        text_fields: Fields to concatenate for embedding. Required with
            embedding_field.
        embedding_dimensions: Vector dimensions. Auto-detected if omitted.

    Returns:
        Dict with "status", "added" count, "errors" count, and provider info.

    Example:
        result = await add_documents(
            index_name="products_idx",
            documents=[{"id": "p1", "title": "Widget", "price": 9.99}],
            prefix="products:",
            embedding_field="embedding",
            text_fields=["title"]
        )
    """
    if Context.readonly_mode():
        return {'status': 'error', 'added': 0, 'reason': 'Readonly mode'}

    if embedding_field and not text_fields:
        return {
            'status': 'error',
            'added': 0,
            'reason': "'text_fields' required when 'embedding_field' is set",
        }

    if prefix is None:
        prefix = f'{index_name}:'

    try:
        r = ValkeyConnectionManager.get_connection(decode_responses=True)
        added = 0
        errors = 0
        actual_dims = embedding_dimensions
        index_checked = False

        for doc in documents:
            doc_id = doc.get(id_field)
            if doc_id is None:
                logging.warning(f"Document missing '{id_field}', skipping")
                errors += 1
                continue

            try:
                mapping: Dict[str, Any] = {}
                for k, v in doc.items():
                    if k == id_field:
                        continue
                    mapping[k] = json.dumps(v) if isinstance(v, (dict, list)) else v

                if embedding_field and text_fields:
                    text = ' '.join(str(doc.get(f, '')) for f in text_fields)
                    provider = _acquire_embeddings_provider()
                    embedding = await provider.generate_embedding(text)

                    if actual_dims is None:
                        actual_dims = len(embedding)
                    if not index_checked:
                        if not _index_exists(r, index_name):
                            _auto_create_index(
                                r,
                                index_name,
                                prefix,
                                embedding_field,
                                actual_dims,
                            )
                        index_checked = True

                    mapping[embedding_field] = pack_embedding(embedding)

                r.hset(f'{prefix}{doc_id}', mapping=mapping)
                added += 1
            except Exception as e:
                logging.warning(f'Failed to process document {doc_id}: {e}')
                errors += 1

        result: Dict[str, Any] = {
            'status': 'success',
            'added': added,
            'errors': errors,
            'index_name': index_name,
        }
        if embedding_field:
            result['embedding_dimensions'] = actual_dims
            result['embeddings_provider'] = _acquire_embeddings_provider().get_provider_name()
        return result

    except Exception as e:
        return {'status': 'error', 'added': 0, 'reason': str(e)}
