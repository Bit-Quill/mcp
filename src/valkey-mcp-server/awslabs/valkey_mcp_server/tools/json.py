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

"""JSON Intelligence tools for Valkey (GLIDE)."""

import json as json_stdlib
import logging
from awslabs.valkey_mcp_server.common.connection import get_client
from awslabs.valkey_mcp_server.common.server import mcp
from awslabs.valkey_mcp_server.context import Context
from typing import Any, Dict, List, Optional, Union


logger = logging.getLogger(__name__)


def _decode(val: Any) -> Any:
    """Decode bytes to string if needed."""
    if isinstance(val, bytes):
        return val.decode()
    return val


@mcp.tool()
async def json_get(
    key: str,
    path: str = '$',
) -> Dict[str, Any]:
    """Get a JSON value at a path from a Valkey key.

    Args:
        key: Valkey key name
        path: JSONPath expression (default: "$" for root)

    Returns:
        Dict with "status" and "value".
    """
    try:
        client = await get_client()
        result = await client.custom_command(['JSON.GET', key, path])
        if result is None:
            return {
                'status': 'error',
                'reason': f"Key '{key}' not found or path '{path}' does not exist",
            }
        decoded = _decode(result)
        try:
            parsed = json_stdlib.loads(decoded)
        except (json_stdlib.JSONDecodeError, TypeError):
            parsed = decoded
        return {'status': 'success', 'value': parsed}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@mcp.tool()
async def json_set(
    key: str,
    value: Union[str, int, float, bool, list, dict, None],
    path: str = '$',
    ttl: Optional[int] = None,
) -> Dict[str, Any]:
    """Set a JSON value at a path on a Valkey key.

    Args:
        key: Valkey key name
        value: JSON-serializable value to set
        path: JSONPath expression (default: "$" for root)
        ttl: Optional TTL in seconds

    Returns:
        Dict with "status".
    """
    if Context.readonly_mode():
        return {'status': 'error', 'reason': 'Readonly mode'}
    try:
        client = await get_client()
        encoded = json_stdlib.dumps(value)
        await client.custom_command(['JSON.SET', key, path, encoded])
        if ttl is not None:
            await client.expire(key, ttl)
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@mcp.tool()
async def json_arrappend(
    key: str,
    values: List[Any],
    path: str = '$',
) -> Dict[str, Any]:
    """Append values to a JSON array at a path.

    Args:
        key: Valkey key name
        values: Values to append to the array
        path: JSONPath expression pointing to an array (default: "$")

    Returns:
        Dict with "status" and "new_length".
    """
    if Context.readonly_mode():
        return {'status': 'error', 'reason': 'Readonly mode'}
    try:
        client = await get_client()
        cmd = ['JSON.ARRAPPEND', key, path] + [json_stdlib.dumps(v) for v in values]
        result = await client.custom_command(cmd)
        length = _decode(result)
        return {'status': 'success', 'new_length': length}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@mcp.tool()
async def json_arrpop(
    key: str,
    path: str = '$',
    index: int = -1,
) -> Dict[str, Any]:
    """Pop an element from a JSON array at a path.

    Args:
        key: Valkey key name
        path: JSONPath expression pointing to an array (default: "$")
        index: Array index to pop (default: -1 for last element)

    Returns:
        Dict with "status" and "popped" value.
    """
    if Context.readonly_mode():
        return {'status': 'error', 'reason': 'Readonly mode'}
    try:
        client = await get_client()
        result = await client.custom_command(['JSON.ARRPOP', key, path, str(index)])
        decoded = _decode(result)
        try:
            parsed = json_stdlib.loads(decoded)
        except (json_stdlib.JSONDecodeError, TypeError):
            parsed = decoded
        return {'status': 'success', 'popped': parsed}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@mcp.tool()
async def json_arrtrim(
    key: str,
    start: int,
    stop: int,
    path: str = '$',
) -> Dict[str, Any]:
    """Trim a JSON array to a specified range.

    Args:
        key: Valkey key name
        start: Start index (inclusive)
        stop: Stop index (inclusive)
        path: JSONPath expression pointing to an array (default: "$")

    Returns:
        Dict with "status" and "new_length".
    """
    if Context.readonly_mode():
        return {'status': 'error', 'reason': 'Readonly mode'}
    try:
        client = await get_client()
        result = await client.custom_command(['JSON.ARRTRIM', key, path, str(start), str(stop)])
        length = _decode(result)
        return {'status': 'success', 'new_length': length}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}
