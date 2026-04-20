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

"""FT.AGGREGATE structured pipeline builder for Valkey Search."""

import logging
from awslabs.valkey_mcp_server.common.connection import ValkeyConnectionManager
from awslabs.valkey_mcp_server.common.server import mcp
from typing import Any, Dict, List, Optional
from valkey.exceptions import ValkeyError


VALID_REDUCE_FUNCTIONS = {
    'COUNT',
    'COUNT_DISTINCT',
    'COUNT_DISTINCTISH',
    'SUM',
    'MIN',
    'MAX',
    'AVG',
    'STDDEV',
    'QUANTILE',
    'TOLIST',
    'FIRST_VALUE',
    'RANDOM_SAMPLE',
}

VALID_STAGE_TYPES = {'GROUPBY', 'SORTBY', 'APPLY', 'FILTER', 'LIMIT'}


def _build_groupby(stage: Dict[str, Any]) -> list:
    """Build GROUPBY ... REDUCE ... args."""
    fields = stage.get('fields', [])
    args = ['GROUPBY', str(len(fields))] + fields

    for reducer in stage.get('reducers', []):
        func = reducer.get('function', '').upper()
        if func not in VALID_REDUCE_FUNCTIONS:
            raise ValueError(
                f"Unknown REDUCE function '{func}'. Must be one of: {VALID_REDUCE_FUNCTIONS}"
            )
        args.append('REDUCE')
        args.append(func)

        # Build reducer arguments
        field = reducer.get('field')
        if func == 'COUNT':
            args.append('0')
        elif func in ('QUANTILE', 'FIRST_VALUE'):
            # These take field + extra arg
            extra = reducer.get('value')
            if field and extra is not None:
                args += ['2', field, str(extra)]
            elif field:
                args += ['1', field]
            else:
                args.append('0')
        elif func == 'RANDOM_SAMPLE':
            sample_size = reducer.get('size', 1)
            if field:
                args += ['2', field, str(sample_size)]
            else:
                args.append('0')
        elif field:
            args += ['1', field]
        else:
            args.append('0')

        alias = reducer.get('alias')
        if alias:
            args += ['AS', alias]

    return args


def _build_sortby(stage: Dict[str, Any]) -> list:
    """Build SORTBY args."""
    fields = stage.get('fields', [])
    sort_args: list = []
    for f in fields:
        if isinstance(f, dict):
            sort_args.append(f.get('field', ''))
            sort_args.append(f.get('order', 'ASC').upper())
        else:
            sort_args += [f, 'ASC']
    args = ['SORTBY', str(len(sort_args))] + sort_args
    if stage.get('max'):
        args += ['MAX', str(stage['max'])]
    return args


def _build_apply(stage: Dict[str, Any]) -> list:
    """Build APPLY expr AS alias."""
    expr = stage.get('expression', '')
    alias = stage.get('alias', '')
    if not expr or not alias:
        raise ValueError("APPLY stage requires 'expression' and 'alias'")
    return ['APPLY', expr, 'AS', alias]


def _build_filter(stage: Dict[str, Any]) -> list:
    """Build FILTER expr."""
    expr = stage.get('expression', '')
    if not expr:
        raise ValueError("FILTER stage requires 'expression'")
    return ['FILTER', expr]


def _build_limit(stage: Dict[str, Any]) -> list:
    """Build LIMIT offset count."""
    return ['LIMIT', str(stage.get('offset', 0)), str(stage.get('count', 10))]


_STAGE_BUILDERS = {
    'GROUPBY': _build_groupby,
    'SORTBY': _build_sortby,
    'APPLY': _build_apply,
    'FILTER': _build_filter,
    'LIMIT': _build_limit,
}


def _parse_aggregate_response(raw) -> List[Dict[str, Any]]:
    """Parse FT.AGGREGATE raw response into list of dicts."""
    if not raw or len(raw) < 2:
        return []
    rows = []
    for row in raw[1:]:
        if not isinstance(row, list):
            continue
        d: Dict[str, Any] = {}
        for i in range(0, len(row) - 1, 2):
            key = row[i].decode() if isinstance(row[i], bytes) else str(row[i])
            val = row[i + 1]
            if isinstance(val, bytes):
                val = val.decode()
            d[key] = val
        rows.append(d)
    return rows


@mcp.tool()
async def aggregate(
    index_name: str,
    query: str = '*',
    pipeline: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run an FT.AGGREGATE pipeline on a Valkey Search index.

    Translates structured JSON pipeline stages into FT.AGGREGATE syntax,
    eliminating the need to know the complex ordered DSL.

    Args:
        index_name: Valkey Search index name
        query: Filter query (default: "*" for all documents)
        pipeline: Ordered list of pipeline stages. Each stage is a dict
            with a "type" key. Supported types:

            GROUPBY — group and aggregate:
              {"type": "GROUPBY", "fields": ["@category"],
               "reducers": [{"function": "COUNT", "alias": "cnt"},
                            {"function": "AVG", "field": "@price", "alias": "avg"}]}

            SORTBY — sort results:
              {"type": "SORTBY",
               "fields": [{"field": "@cnt", "order": "DESC"}]}

            APPLY — computed expression:
              {"type": "APPLY", "expression": "@price * 1.1",
               "alias": "adjusted"}

            FILTER — post-aggregation filter:
              {"type": "FILTER", "expression": "@cnt > 5"}

            LIMIT — pagination:
              {"type": "LIMIT", "offset": 0, "count": 10}

    Returns:
        Dict with "status" and "results" (list of row dicts).

    Example:
        result = await aggregate(
            index_name="products_idx",
            query="*",
            pipeline=[
                {"type": "GROUPBY", "fields": ["@category"],
                 "reducers": [{"function": "COUNT", "alias": "count"}]},
                {"type": "SORTBY",
                 "fields": [{"field": "@count", "order": "DESC"}]},
                {"type": "LIMIT", "offset": 0, "count": 5}
            ]
        )
    """
    try:
        r = ValkeyConnectionManager.get_connection(decode_responses=False)
        cmd: list = ['FT.AGGREGATE', index_name, query]

        if pipeline:
            for i, stage in enumerate(pipeline):
                stype = stage.get('type', '').upper()
                if stype not in VALID_STAGE_TYPES:
                    return {
                        'status': 'error',
                        'reason': (
                            f"Stage {i}: unknown type '{stype}'. Must be: {VALID_STAGE_TYPES}"
                        ),
                    }
                builder = _STAGE_BUILDERS[stype]
                try:
                    cmd += builder(stage)
                except ValueError as e:
                    return {
                        'status': 'error',
                        'reason': f'Stage {i} ({stype}): {e}',
                    }

        raw = r.execute_command(*cmd)
        rows = _parse_aggregate_response(raw)
        total = raw[0] if raw else 0

        return {
            'status': 'success',
            'results': rows,
            'total': int(total),
        }

    except ValkeyError as e:
        return {'status': 'error', 'reason': str(e)}
    except Exception as e:
        logging.exception(f'aggregate failed: {e}')
        return {'status': 'error', 'reason': str(e)}
