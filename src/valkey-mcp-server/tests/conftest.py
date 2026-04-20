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

"""Shared fixtures for integration tests using testcontainers."""

import pytest
from unittest.mock import patch


@pytest.fixture(scope='session')
def valkey_container():
    """Start a valkey-bundle container for the test session.

    Uses testcontainers RedisContainer with the valkey/valkey-bundle image,
    which includes FT.* search and JSON modules.
    """
    from testcontainers.redis import RedisContainer

    with RedisContainer(image='valkey/valkey-bundle:unstable') as container:
        yield container


@pytest.fixture()
def valkey_connection(valkey_container):
    """Patch ValkeyConnectionManager to use the testcontainer.

    Returns the live Valkey connection for direct use in tests.
    """
    from valkey import Valkey

    host = valkey_container.get_container_host_ip()
    port = int(valkey_container.get_exposed_port(6379))

    def make_connection(decode_responses=True):
        return Valkey(host=host, port=port, decode_responses=decode_responses)

    with patch(
        'awslabs.valkey_mcp_server.common.connection.ValkeyConnectionManager.get_connection',
        side_effect=make_connection,
    ):
        conn = make_connection(decode_responses=True)
        yield conn
        # Flush between tests
        conn.flushall()
