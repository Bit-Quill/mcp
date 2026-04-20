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

"""Integration tests for add_documents, search, and aggregate tools.

Uses valkey-bundle:unstable which supports TEXT fields and FT.AGGREGATE.
Note: FT.AGGREGATE does not support '*' wildcard — use actual filter queries.
"""

import hashlib
import pytest
import time
from awslabs.valkey_mcp_server.tools.search_add_documents import add_documents
from awslabs.valkey_mcp_server.tools.search_aggregate import aggregate
from awslabs.valkey_mcp_server.tools.search_manage_index import manage_index
from awslabs.valkey_mcp_server.tools.search_query import search
from unittest.mock import AsyncMock, Mock, patch


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_FAKE_DIM = 4


def _fake_embedding(text: str):
    """Deterministic 4-dim embedding from text hash."""
    h = hashlib.md5(text.encode()).digest()
    return [b / 255.0 for b in h[:_FAKE_DIM]]


@pytest.fixture()
def mock_embeddings():
    """Patch embeddings provider with a deterministic fake."""
    provider = Mock()
    provider.generate_embedding = AsyncMock(side_effect=_fake_embedding)
    provider.get_provider_name = Mock(return_value='fake')
    provider.get_dimensions = Mock(return_value=_FAKE_DIM)

    with (
        patch(
            'awslabs.valkey_mcp_server.tools.search_add_documents._acquire_embeddings_provider',
            return_value=provider,
        ),
        patch(
            'awslabs.valkey_mcp_server.tools.search_query._acquire_provider',
            return_value=provider,
        ),
        patch(
            'awslabs.valkey_mcp_server.tools.search_query._has_provider',
            return_value=True,
        ),
    ):
        yield provider


class TestAddDocumentsIntegration:
    """Integration tests for add_documents."""

    async def test_add_plain_documents(self, valkey_connection):
        """Add documents without embeddings as plain hashes."""
        await manage_index(
            action='create',
            index_name='plain_idx',
            schema=[{'name': 'title', 'type': 'TEXT'}],
            prefix=['plain:'],
        )
        result = await add_documents(
            index_name='plain_idx',
            documents=[
                {'id': '1', 'title': 'First doc'},
                {'id': '2', 'title': 'Second doc'},
            ],
            prefix='plain:',
        )
        assert result['status'] == 'success'
        assert result['added'] == 2
        assert result['errors'] == 0

    async def test_add_with_embeddings(self, valkey_connection, mock_embeddings):
        """Add documents with embedding generation."""
        result = await add_documents(
            index_name='emb_idx',
            documents=[
                {'id': 'a', 'title': 'Hello world', 'body': 'Test content'},
                {'id': 'b', 'title': 'Goodbye', 'body': 'More content'},
            ],
            prefix='emb:',
            embedding_field='embedding',
            text_fields=['title', 'body'],
        )
        assert result['status'] == 'success'
        assert result['added'] == 2
        assert result['embedding_dimensions'] == _FAKE_DIM
        assert result['embeddings_provider'] == 'fake'

    async def test_add_missing_id(self, valkey_connection):
        """Documents without id field are skipped."""
        result = await add_documents(
            index_name='noid_idx',
            documents=[{'title': 'No ID here'}],
            prefix='noid:',
        )
        assert result['added'] == 0
        assert result['errors'] == 1

    async def test_auto_creates_index(self, valkey_connection, mock_embeddings):
        """Index is auto-created when embedding_field is set."""
        result = await add_documents(
            index_name='auto_idx',
            documents=[{'id': 'x', 'title': 'Auto create'}],
            prefix='auto:',
            embedding_field='embedding',
            text_fields=['title'],
        )
        assert result['status'] == 'success'
        assert result['added'] == 1

        info = await manage_index(action='info', index_name='auto_idx')
        assert info['status'] == 'success'


class TestSearchIntegration:
    """Integration tests for the unified search tool."""

    async def test_text_search(self, valkey_connection):
        """Text search when no embedding provider is available."""
        await manage_index(
            action='create',
            index_name='txt_idx',
            schema=[{'name': 'title', 'type': 'TEXT'}],
            prefix=['txt:'],
        )
        await add_documents(
            index_name='txt_idx',
            documents=[
                {'id': '1', 'title': 'machine learning basics'},
                {'id': '2', 'title': 'cooking recipes'},
                {'id': '3', 'title': 'advanced machine learning'},
            ],
            prefix='txt:',
        )
        time.sleep(0.5)

        with patch(
            'awslabs.valkey_mcp_server.tools.search_query._has_provider',
            return_value=False,
        ):
            result = await search(
                index_name='txt_idx',
                query_text='machine learning',
            )
        assert result['status'] == 'success'
        assert result['mode'] == 'text'
        assert len(result['results']) >= 2

    async def test_semantic_search(self, valkey_connection, mock_embeddings):
        """Semantic search with fake embeddings."""
        await add_documents(
            index_name='sem_idx',
            documents=[
                {'id': '1', 'title': 'cats and dogs'},
                {'id': '2', 'title': 'fish and birds'},
            ],
            prefix='sem:',
            embedding_field='embedding',
            text_fields=['title'],
        )
        time.sleep(0.5)

        result = await search(
            index_name='sem_idx',
            query_text='animals',
            vector_field='embedding',
        )
        assert result['status'] == 'success'
        assert result['mode'] == 'semantic'
        assert len(result['results']) >= 1

    async def test_search_no_params_error(self, valkey_connection):
        """Search without query_text or document_id returns error."""
        result = await search(index_name='any')
        assert result['status'] == 'error'

    async def test_find_similar(self, valkey_connection, mock_embeddings):
        """Find-similar mode using an existing document's vector."""
        await add_documents(
            index_name='sim_idx',
            documents=[
                {'id': '1', 'title': 'alpha'},
                {'id': '2', 'title': 'alpha beta'},
                {'id': '3', 'title': 'gamma delta'},
            ],
            prefix='sim:',
            embedding_field='embedding',
            text_fields=['title'],
        )
        time.sleep(0.5)

        result = await search(
            index_name='sim_idx',
            document_id='sim:1',
            vector_field='embedding',
        )
        assert result['status'] == 'success'
        assert result['mode'] == 'find_similar'
        ids = [r.get('id') for r in result['results']]
        assert 'sim:1' not in ids


class TestAggregateIntegration:
    """Integration tests for the aggregate tool.

    Note: valkey-search FT.AGGREGATE does not support '*' wildcard queries.
    Use actual filter expressions (TAG, NUMERIC, TEXT queries).
    """

    async def _seed_products(self, valkey_connection):
        """Seed product data for aggregate tests."""
        await manage_index(
            action='create',
            index_name='prod_idx',
            schema=[
                {'name': 'title', 'type': 'TEXT'},
                {'name': 'category', 'type': 'TAG'},
                {'name': 'price', 'type': 'NUMERIC', 'sortable': True},
            ],
            prefix=['prod:'],
        )
        await add_documents(
            index_name='prod_idx',
            documents=[
                {'id': '1', 'category': 'electronics', 'price': 100, 'title': 'phone'},
                {'id': '2', 'category': 'electronics', 'price': 200, 'title': 'laptop'},
                {'id': '3', 'category': 'books', 'price': 15, 'title': 'novel'},
                {'id': '4', 'category': 'books', 'price': 25, 'title': 'textbook'},
                {'id': '5', 'category': 'books', 'price': 10, 'title': 'comic'},
            ],
            prefix='prod:',
        )
        time.sleep(0.5)

    async def test_groupby_count(self, valkey_connection):
        """GROUPBY with COUNT reducer using numeric range filter."""
        await self._seed_products(valkey_connection)
        result = await aggregate(
            index_name='prod_idx',
            query='@price:[0 500]',
            pipeline=[
                {
                    'type': 'GROUPBY',
                    'fields': ['@category'],
                    'reducers': [{'function': 'COUNT', 'alias': 'cnt'}],
                },
            ],
        )
        assert result['status'] == 'success'
        assert len(result['results']) >= 1
        # Verify COUNT reducer works
        total = sum(int(r['cnt']) for r in result['results'])
        assert total == 5

    async def test_groupby_avg(self, valkey_connection):
        """GROUPBY with AVG reducer on filtered set."""
        await self._seed_products(valkey_connection)
        result = await aggregate(
            index_name='prod_idx',
            query='@category:{electronics}',
            pipeline=[
                {
                    'type': 'GROUPBY',
                    'fields': ['@category'],
                    'reducers': [
                        {'function': 'AVG', 'field': '@price', 'alias': 'avg_price'},
                    ],
                },
            ],
        )
        assert result['status'] == 'success'
        assert len(result['results']) >= 1
        assert 'avg_price' in result['results'][0]

    async def test_apply_and_limit(self, valkey_connection):
        """APPLY expression and LIMIT stage."""
        await self._seed_products(valkey_connection)
        result = await aggregate(
            index_name='prod_idx',
            query='@price:[0 500]',
            pipeline=[
                {
                    'type': 'GROUPBY',
                    'fields': ['@category'],
                    'reducers': [
                        {'function': 'SUM', 'field': '@price', 'alias': 'total'},
                    ],
                },
                {'type': 'APPLY', 'expression': '@total * 1.1', 'alias': 'with_tax'},
                {'type': 'LIMIT', 'offset': 0, 'count': 1},
            ],
        )
        assert result['status'] == 'success'
        assert len(result['results']) == 1
        assert 'with_tax' in result['results'][0]

    async def test_tag_filter_aggregate(self, valkey_connection):
        """Aggregate with TAG filter."""
        await self._seed_products(valkey_connection)
        result = await aggregate(
            index_name='prod_idx',
            query='@category:{electronics}',
            pipeline=[
                {
                    'type': 'GROUPBY',
                    'fields': ['@category'],
                    'reducers': [{'function': 'COUNT', 'alias': 'cnt'}],
                },
            ],
        )
        assert result['status'] == 'success'
        assert len(result['results']) == 1
        assert result['results'][0]['cnt'] == '2'

    async def test_invalid_stage_type(self, valkey_connection):
        """Invalid stage type returns error before hitting Valkey."""
        result = await aggregate(
            index_name='any',
            pipeline=[{'type': 'BOGUS'}],
        )
        assert result['status'] == 'error'
        assert 'BOGUS' in result['reason']
