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

"""Integration tests for manage_index tool against valkey-bundle:unstable.

Uses the unstable tag which supports TEXT fields and FT.AGGREGATE.
"""

import pytest
from awslabs.valkey_mcp_server.tools.search_manage_index import manage_index


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestManageIndexIntegration:
    """Integration tests for manage_index against a real Valkey instance."""

    async def test_create_and_info(self, valkey_connection):
        """Create an index with TEXT + VECTOR and verify via info."""
        result = await manage_index(
            action='create',
            index_name='test_idx',
            schema=[
                {'name': 'title', 'type': 'TEXT'},
                {'name': 'category', 'type': 'TAG'},
                {'name': 'year', 'type': 'NUMERIC'},
                {'name': 'embedding', 'type': 'VECTOR', 'dimensions': 4},
            ],
            prefix=['doc:'],
        )
        assert result['status'] == 'success'
        assert result['created'] is True

        info = await manage_index(action='info', index_name='test_idx')
        assert info['status'] == 'success'
        assert info['info']['index_name'] == 'test_idx'

    async def test_create_text_only_index(self, valkey_connection):
        """Create a TEXT-only index (no VECTOR field)."""
        result = await manage_index(
            action='create',
            index_name='text_only_idx',
            schema=[{'name': 'title', 'type': 'TEXT'}],
            prefix=['txt:'],
        )
        assert result['status'] == 'success'

    async def test_list_indices(self, valkey_connection):
        """Create indices and list them."""
        await manage_index(
            action='create',
            index_name='list_a',
            schema=[{'name': 'v', 'type': 'VECTOR', 'dimensions': 4}],
        )
        await manage_index(
            action='create',
            index_name='list_b',
            schema=[{'name': 'f', 'type': 'TEXT'}],
        )
        result = await manage_index(action='list')
        assert result['status'] == 'success'
        assert 'list_a' in result['indices']
        assert 'list_b' in result['indices']

    async def test_drop_index(self, valkey_connection):
        """Create then drop an index."""
        await manage_index(
            action='create',
            index_name='drop_me',
            schema=[{'name': 'f', 'type': 'TEXT'}],
        )
        result = await manage_index(action='drop', index_name='drop_me')
        assert result['status'] == 'success'
        assert result['dropped'] is True

        info = await manage_index(action='info', index_name='drop_me')
        assert info['status'] == 'error'

    async def test_create_with_all_supported_field_types(self, valkey_connection):
        """Create index with TEXT, NUMERIC, TAG, and VECTOR fields."""
        result = await manage_index(
            action='create',
            index_name='types_idx',
            schema=[
                {'name': 'title', 'type': 'TEXT'},
                {'name': 'count', 'type': 'NUMERIC', 'sortable': True},
                {'name': 'tags', 'type': 'TAG', 'separator': ','},
                {
                    'name': 'vec',
                    'type': 'VECTOR',
                    'dimensions': 8,
                    'distance_metric': 'L2',
                    'structure_type': 'FLAT',
                },
            ],
            prefix=['item:'],
        )
        assert result['status'] == 'success'

    async def test_create_missing_schema(self, valkey_connection):
        """Create without schema returns error."""
        result = await manage_index(action='create', index_name='bad')
        assert result['status'] == 'error'
        assert 'schema' in result['reason'].lower()

    async def test_unknown_action(self, valkey_connection):
        """Unknown action returns error."""
        result = await manage_index(action='bogus', index_name='x')
        assert result['status'] == 'error'
        assert 'bogus' in result['reason'].lower()
