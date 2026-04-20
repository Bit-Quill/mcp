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

"""Index management tool for Valkey Search."""

import logging
from awslabs.valkey_mcp_server.common.connection import ValkeyConnectionManager
from awslabs.valkey_mcp_server.common.server import mcp
from awslabs.valkey_mcp_server.context import Context
from typing import Any, Dict, List, Optional
from valkey.exceptions import ValkeyError


VALID_FIELD_TYPES = {'TEXT', 'NUMERIC', 'TAG', 'GEO', 'VECTOR'}
VALID_DISTANCE_METRICS = {'COSINE', 'L2', 'IP'}
VALID_STRUCTURE_TYPES = {'FLAT', 'HNSW'}
VALID_INDEX_TYPES = {'HASH', 'JSON'}


def _build_field_args(
    field: Dict[str, Any],
    structure_type: str,
    distance_metric: str,
) -> list:
    """Translate a schema field dict into FT.CREATE field arguments."""
    name = field['name']
    ftype = field.get('type', 'TEXT').upper()
    if ftype not in VALID_FIELD_TYPES:
        raise ValueError(
            f"Invalid field type '{ftype}' for '{name}'. Must be one of: {VALID_FIELD_TYPES}"
        )

    args: list = [name]
    alias = field.get('alias')
    if alias:
        args += ['AS', alias]

    if ftype == 'VECTOR':
        dims = field.get('dimensions')
        if not dims:
            raise ValueError(f"VECTOR field '{name}' requires 'dimensions'")
        st = field.get('structure_type', structure_type).upper()
        dm = field.get('distance_metric', distance_metric).upper()
        sub = ['TYPE', 'FLOAT32', 'DIM', str(dims), 'DISTANCE_METRIC', dm]
        if field.get('initial_cap') is not None:
            sub += ['INITIAL_CAP', str(field['initial_cap'])]
        if st == 'HNSW':
            for param, key in [
                ('M', 'max_outgoing_edges'),
                ('EF_CONSTRUCTION', 'ef_construction'),
                ('EF_RUNTIME', 'ef_runtime'),
            ]:
                if field.get(key) is not None:
                    sub += [param, str(field[key])]
        args += ['VECTOR', st, str(len(sub))] + sub
    else:
        args.append(ftype)
        if field.get('sortable'):
            args.append('SORTABLE')
        if field.get('noindex'):
            args.append('NOINDEX')
        if ftype == 'TAG' and field.get('separator'):
            args += ['SEPARATOR', field['separator']]
        if ftype == 'TEXT':
            if field.get('weight') is not None:
                args += ['WEIGHT', str(field['weight'])]
            if field.get('nostem'):
                args.append('NOSTEM')

    return args


def _parse_info(raw: list) -> Dict[str, Any]:
    """Parse FT.INFO raw response into a structured dict."""
    result: Dict[str, Any] = {}
    for i in range(0, len(raw) - 1, 2):
        key = raw[i].decode() if isinstance(raw[i], bytes) else str(raw[i])
        val = raw[i + 1]
        if isinstance(val, bytes):
            val = val.decode()
        elif isinstance(val, list):
            val = [v.decode() if isinstance(v, bytes) else v for v in val]
        result[key] = val
    return result


@mcp.tool()
async def manage_index(
    action: str,
    index_name: Optional[str] = None,
    schema: Optional[List[Dict[str, Any]]] = None,
    prefix: Optional[List[str]] = None,
    index_type: str = 'HASH',
    structure_type: str = 'HNSW',
    distance_metric: str = 'COSINE',
) -> Dict[str, Any]:
    """Manage Valkey Search indices: create, drop, inspect, or list.

    Handles FT.CREATE, FT.DROPINDEX, FT.INFO, and FT._LIST through structured
    input, eliminating the need to construct raw Valkey search syntax.

    Args:
        action: "create", "drop", "info", or "list"
        index_name: Index name (required for create, drop, info)
        schema: Field definitions for create. Each field dict needs "name" and
            "type" (TEXT, NUMERIC, TAG, GEO, VECTOR). VECTOR fields also need
            "dimensions". Example:
            [{"name": "title", "type": "TEXT", "sortable": true},
             {"name": "embedding", "type": "VECTOR", "dimensions": 768},
             {"name": "year", "type": "NUMERIC"},
             {"name": "category", "type": "TAG"}]
        prefix: Key prefix filter (e.g., ["docs:"])
        index_type: "HASH" (default) or "JSON"
        structure_type: Vector algorithm — "HNSW" (default) or "FLAT"
        distance_metric: Vector metric — "COSINE" (default), "L2", or "IP"

    Returns:
        Dict with "status" ("success"/"error") and action-specific data.
    """
    action = action.lower()
    try:
        r = ValkeyConnectionManager.get_connection(decode_responses=False)

        if action == 'list':
            raw = r.execute_command('FT._LIST')
            names = [i.decode() if isinstance(i, bytes) else str(i) for i in (raw or [])]
            return {'status': 'success', 'indices': names}

        if not index_name:
            return {
                'status': 'error',
                'reason': f"'index_name' required for '{action}'",
            }

        if action == 'info':
            raw = r.execute_command('FT.INFO', index_name)
            return {
                'status': 'success',
                'index_name': index_name,
                'info': _parse_info(raw),
            }

        if action == 'drop':
            if Context.readonly_mode():
                return {'status': 'error', 'reason': 'Readonly mode'}
            r.execute_command('FT.DROPINDEX', index_name)
            return {'status': 'success', 'index_name': index_name, 'dropped': True}

        if action == 'create':
            if Context.readonly_mode():
                return {'status': 'error', 'reason': 'Readonly mode'}
            if not schema:
                return {'status': 'error', 'reason': "'schema' required for create"}

            it = index_type.upper()
            st = structure_type.upper()
            dm = distance_metric.upper()
            for val, name, valid in [
                (it, 'index_type', VALID_INDEX_TYPES),
                (st, 'structure_type', VALID_STRUCTURE_TYPES),
                (dm, 'distance_metric', VALID_DISTANCE_METRICS),
            ]:
                if val not in valid:
                    return {
                        'status': 'error',
                        'reason': f"Invalid {name} '{val}'. Must be: {valid}",
                    }

            cmd: list = ['FT.CREATE', index_name, 'ON', it]
            if prefix:
                cmd += ['PREFIX', str(len(prefix))] + prefix
            cmd.append('SCHEMA')
            for f in schema:
                if 'name' not in f:
                    return {
                        'status': 'error',
                        'reason': "Each field needs a 'name' key",
                    }
                cmd += _build_field_args(f, st, dm)

            r.execute_command(*cmd)
            return {
                'status': 'success',
                'index_name': index_name,
                'created': True,
            }

        return {
            'status': 'error',
            'reason': f"Unknown action '{action}'. Use: create, drop, info, list",
        }

    except ValkeyError as e:
        return {'status': 'error', 'reason': str(e)}
    except Exception as e:
        logging.exception(f'manage_index failed: {e}')
        return {'status': 'error', 'reason': str(e)}
