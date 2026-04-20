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

"""Unified search tool — semantic, text, hybrid, and find-similar."""

import json
import logging
import struct
from awslabs.valkey_mcp_server.common.connection import ValkeyConnectionManager
from awslabs.valkey_mcp_server.common.server import mcp
from awslabs.valkey_mcp_server.common.utils import pack_embedding
from awslabs.valkey_mcp_server.embeddings import create_embeddings_provider
from typing import Any, Dict, List, Optional
from valkey.commands.search.query import Query
from valkey.exceptions import ValkeyError


_embeddings_provider = None


def _acquire_provider():
    global _embeddings_provider
    if _embeddings_provider is None:
        _embeddings_provider = create_embeddings_provider()
    return _embeddings_provider


def _has_provider() -> bool:
    try:
        _acquire_provider()
        return True
    except Exception:
        return False


def _parse_docs(docs, return_fields=None) -> List[Dict[str, Any]]:
    """Parse FT.SEARCH result documents into dicts."""
    results = []
    for doc in docs:
        d: Dict[str, Any] = {'id': doc.id}
        for attr in dir(doc):
            if attr.startswith('_') or attr in ('id', 'payload'):
                continue
            val = getattr(doc, attr, None)
            if val is None or callable(val):
                continue
            if isinstance(val, bytes):
                try:
                    val = val.decode('utf-8')
                except UnicodeDecodeError:
                    continue
            if isinstance(val, str) and val.startswith(('{', '[')):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
            d[attr] = val
        if return_fields:
            d = {k: v for k, v in d.items() if k in return_fields or k == 'id'}
        results.append(d)
    return results


@mcp.tool()
async def search(
    index_name: str,
    query_text: Optional[str] = None,
    document_id: Optional[str] = None,
    vector_field: str = 'embedding',
    filter_expression: Optional[str] = None,
    return_fields: Optional[List[str]] = None,
    offset: int = 0,
    limit: int = 10,
    hybrid_weight: float = 0.5,
) -> Dict[str, Any]:
    """Search a Valkey Search index with auto-detected mode.

    Modes (auto-detected from parameters):

    - Semantic: query_text + embedding provider configured
    - Text: query_text + no embedding provider
    - Find-similar: document_id provided
    - Hybrid: query_text + hybrid_weight != 0.5

    Args:
        index_name: Valkey Search index name
        query_text: Natural language or text query
        document_id: Key of existing document for find-similar
        vector_field: Vector field name (default: "embedding")
        filter_expression: Valkey filter (e.g., "@year:[2020 2024]")
        return_fields: Fields to return. None = all.
        offset: Pagination offset (default: 0)
        limit: Max results (default: 10)
        hybrid_weight: Text vs vector balance, 0=text 1=vector (default: 0.5)

    Returns:
        Dict with "status", "mode", and "results" list.
    """
    if not query_text and not document_id:
        return {
            'status': 'error',
            'reason': "Provide 'query_text' or 'document_id'",
        }
    if filter_expression and '=>' in filter_expression:
        return {
            'status': 'error',
            'reason': "'=>' not allowed in filter_expression",
        }

    try:
        r = ValkeyConnectionManager.get_connection(decode_responses=False)
        ft = r.ft(index_name)

        if document_id:
            return await _find_similar(
                r,
                ft,
                document_id,
                vector_field,
                filter_expression,
                return_fields,
                offset,
                limit,
            )

        has = _has_provider()
        if has and hybrid_weight != 0.5:
            return await _hybrid(
                ft,
                query_text,
                vector_field,
                filter_expression,
                return_fields,
                offset,
                limit,
                hybrid_weight,
            )
        if has:
            return await _semantic(
                ft,
                query_text,
                vector_field,
                filter_expression,
                return_fields,
                offset,
                limit,
            )
        return await _text(
            ft,
            query_text,
            filter_expression,
            return_fields,
            offset,
            limit,
        )

    except ValkeyError as e:
        return {'status': 'error', 'reason': str(e)}
    except Exception as e:
        logging.exception(f'search failed: {e}')
        return {'status': 'error', 'reason': str(e)}


async def _semantic(ft, query_text, vector_field, filt, ret, offset, limit):
    provider = _acquire_provider()
    emb = await provider.generate_embedding(query_text)
    blob = pack_embedding(emb)
    f = filt or '*'
    q = Query(f'{f}=>[KNN {limit} @{vector_field} $blob]').paging(offset, limit)
    res = ft.search(q, query_params={'blob': blob})
    docs = _parse_docs(res.docs, ret) if hasattr(res, 'docs') else []
    return {
        'status': 'success',
        'mode': 'semantic',
        'results': docs,
        'total': getattr(res, 'total', len(docs)),
    }


async def _text(ft, query_text, filt, ret, offset, limit):
    qs = f'({filt}) {query_text}' if filt else query_text
    q = Query(qs).paging(offset, limit)
    res = ft.search(q)
    docs = _parse_docs(res.docs, ret) if hasattr(res, 'docs') else []
    return {
        'status': 'success',
        'mode': 'text',
        'results': docs,
        'total': getattr(res, 'total', len(docs)),
    }


async def _find_similar(r, ft, doc_id, vector_field, filt, ret, offset, limit):
    raw = r.hget(doc_id, vector_field.encode())
    if not raw:
        return {
            'status': 'error',
            'reason': f"'{doc_id}' not found or no '{vector_field}' field",
        }
    n = len(raw) // 4
    emb = list(struct.unpack(f'{n}f', raw))
    blob = pack_embedding(emb)
    f = filt or '*'
    q = Query(f'{f}=>[KNN {limit + 1} @{vector_field} $blob]').paging(
        offset,
        limit + 1,
    )
    res = ft.search(q, query_params={'blob': blob})
    docs = _parse_docs(res.docs, ret) if hasattr(res, 'docs') else []
    docs = [d for d in docs if d.get('id') != doc_id][:limit]
    return {
        'status': 'success',
        'mode': 'find_similar',
        'results': docs,
        'total': len(docs),
    }


async def _hybrid(ft, query_text, vector_field, filt, ret, offset, limit, weight):
    provider = _acquire_provider()
    emb = await provider.generate_embedding(query_text)
    blob = pack_embedding(emb)
    tf = f'({filt}) {query_text}' if filt else query_text
    q = Query(f'{tf}=>[KNN {limit} @{vector_field} $blob]').paging(offset, limit)
    res = ft.search(q, query_params={'blob': blob})
    docs = _parse_docs(res.docs, ret) if hasattr(res, 'docs') else []
    return {
        'status': 'success',
        'mode': 'hybrid',
        'hybrid_weight': weight,
        'results': docs,
        'total': getattr(res, 'total', len(docs)),
    }
