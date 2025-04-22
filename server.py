import json
import logging
from http import HTTPMethod
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP

from config import CLUSTERIQ_API_TIMEOUT, CLUSTERIQ_API_URL
from logger import setup_logging

setup_logging()
log = logging.getLogger(__name__)

mcp = FastMCP("ClusterIQ")


async def _call_clusteriq_api(
    ctx: Context,
    method: HTTPMethod,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Helper function to make asynchronous HTTP requests to the ClusterIQ API.

    Handles client creation, request execution, error handling, and JSON parsing.

    Args:
        ctx: The MCP Context for logging.
        method: HTTP method (e.g., "GET", "POST").
        path: API path (e.g., "/overview", "/accounts"). Should start with '/'.
        params: Optional dictionary of query parameters.
        json_data: Optional dictionary for the JSON request body.

    Returns:
        The parsed JSON response body.

    Raises:
        httpx.HTTPStatusError: If the API returns an error status code.
        Exception: For other network or unexpected errors.
    """
    base_url = CLUSTERIQ_API_URL.rstrip("/")
    full_url = f"{base_url}{path}"
    await ctx.info(
        f"Calling API {method} {full_url}"
        + (f" with params: {params}" if params else "")
        + (f" and JSON body: {json_data}" if json_data else ""),
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=method,
                url=full_url,
                params=params,
                json=json_data,
                timeout=CLUSTERIQ_API_TIMEOUT,
            )
            response.raise_for_status()
            await ctx.info(
                f"API call successful: {method} {path} ({response.status_code})"
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            await ctx.error(f"API Error {e.response.status_code}: {e.response.text}")
            raise

        except httpx.RequestError as e:
            await ctx.error(f"API Request Error: {str(e)}")
            raise

        except json.JSONDecodeError as e:
            await ctx.error(f"API JSON decode error: {str(e)}")
            raise

        except Exception as e:
            await ctx.error(f"API Unexpected error: {str(e)}")
            raise


@mcp.tool(
    description="Retrieves a summary of the cloud inventory, including counts of running/stopped/archived clusters, total instances, and provider details"
)
async def get_inventory_overview(ctx: Context) -> Dict[str, Any]:
    """
    Retrieves a summary of the cloud inventory from the /overview endpoint.
    Includes counts of running/stopped/archived clusters, total instances, and provider details.

    Args:
        ctx: The MCP context object (provides logging, etc.).

    Returns:
        A dictionary containing the inventory overview summary.

    Raises:
        httpx.HTTPStatusError: If the API returns an error status code (4xx, 5xx).
        Exception: For other potential network or JSON parsing errors.
    """
    log.debug("*** Entering Tool Function: get_inventory_overview ***")
    return await _call_clusteriq_api(ctx=ctx, path="/overview", method=HTTPMethod.GET)


@mcp.tool(
    description="Retrieves a list of all inventory accounts or details for a specific account by name"
)
async def get_accounts(
    ctx: Context, account_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves account-level inventory data.

    If an account name is provided, returns details for that specific account.
    Otherwise, returns a list of all available accounts.

    Args:
        ctx: MCP Context used for logging and tool execution.
        account_name: Optional account identifier to filter the results.

    Returns:
        A dictionary with:
            - 'clusters': list of account dictionaries
            - 'count': total number of accounts retrieved

    Raises:
        httpx.HTTPStatusError: If the ClusterIQ API responds with an error.
        Exception: For network, JSON, or unexpected processing errors.
    """
    log.debug("*** Entering Tool Function: get_accounts ***")
    if account_name:
        path = f"/accounts/{account_name}"
    else:
        path = "/accounts"
    api_response = await _call_clusteriq_api(ctx, method=HTTPMethod.GET, path=path)
    accounts_list = api_response.get("accounts", [])
    return {"clusters": accounts_list, "count": len(accounts_list)}


@mcp.tool(
    description="Retrieves a list of all inventory clusters or details for a specific cluster by name"
)
async def get_clusters(
    ctx: Context, cluster_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves cluster-level inventory data.

    If a specific cluster name is given, returns detailed info for that cluster.
    Otherwise, returns the full list of discovered clusters.

    Args:
        ctx: MCP Context used for logging and execution context.
        cluster_name: Optional cluster identifier to narrow the query.

    Returns:
        A dictionary with:
            - 'clusters': list of cluster dictionaries
            - 'count': total number of clusters retrieved

    Raises:
        httpx.HTTPStatusError: If the ClusterIQ API responds with a client/server error.
        Exception: For connection, JSON parsing, or runtime issues.
    """
    log.debug("*** Entering Tool Function: get_clusters ***")
    if cluster_name:
        path = f"/clusters/{cluster_name}"
    else:
        path = "/clusters"
    api_response = await _call_clusteriq_api(ctx, method=HTTPMethod.GET, path=path)
    clusters_list = api_response.get("clusters", [])
    return {"clusters": clusters_list, "count": len(clusters_list)}


@mcp.tool(
    description="Retrieves a list of all inventory instances or details for a specific instance by name"
)
async def get_instances(
    ctx: Context, cluster_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves instance-level inventory data.

    If a cluster name is provided, returns instances associated with that cluster.
    Otherwise, returns the full list of instances across all clusters.

    Args:
        ctx: MCP Context used for structured logging and tool invocation.
        cluster_name: Optional cluster identifier to filter instances by cluster.

    Returns:
        A dictionary with:
            - 'instances': list of instance dictionaries
            - 'count': total number of instances retrieved

    Raises:
        httpx.HTTPStatusError: If the ClusterIQ API returns an error status.
        Exception: For networking, JSON parsing, or unexpected runtime errors.
    """
    log.debug("*** Entering Tool Function: get_instances ***")
    if cluster_name:
        path = f"/instances/{cluster_name}"
    else:
        path = "/instances"
    api_response = await _call_clusteriq_api(ctx, method=HTTPMethod.GET, path=path)
    instances_list = api_response.get("instances", [])
    return {"instances": instances_list, "count": len(instances_list)}


if __name__ == "__main__":
    log.info("MCP server: starting run loop")
    mcp.run()
