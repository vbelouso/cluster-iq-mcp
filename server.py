import requests
from mcp.server import FastMCP
from mcp.server.fastmcp.prompts import base

from config import CLUSTERIQ_API_URL

mcp = FastMCP("ClusterIQ")


@mcp.resource("clusters://list")
def get_clusters():
    url = f"{CLUSTERIQ_API_URL}/clusters"
    response = requests.get(url)
    response.raise_for_status()

    clusters = response.json()["clusters"]
    lines = [
        f"{c['name']} ({c['provider']}) — {c['status']}, {c['region']}, {c['instanceCount']} instances"
        for c in clusters
    ]
    return "\n".join(lines)


@mcp.resource("instances://list")
def get_instances():
    url = f"{CLUSTERIQ_API_URL}/instances"
    response = requests.get(url)
    response.raise_for_status()
    instances = response.json()["instances"]
    lines = [
        f"{i['id']} [{i['instanceType']}] — {i['status']}, {i['availabilityZone']}, "
        f"Cluster: {i.get('clusterID', 'N/A')}, Age: {i['age']}d"
        for i in instances[:50]  # just for the testing
    ]
    return "\n".join(lines)


@mcp.resource("accounts://summary")
def get_accounts() -> str:
    url = f"{CLUSTERIQ_API_URL}/accounts"
    response = requests.get(url)
    response.raise_for_status()

    accounts = response.json()["accounts"]
    lines = [
        f"{a['name']} ({a['provider']}) — {a['clusterCount']} clusters, ${a['totalCost']:.2f}"
        for a in accounts
    ]
    return "\n".join(lines)


@mcp.resource("summary://overview")
def get_status_summary() -> str:
    url = f"{CLUSTERIQ_API_URL}/overview"
    response = requests.get(url)
    response.raise_for_status()

    overview = response.json()
    clusters = overview["clusters"]
    instances = overview["instances"]
    providers = overview["providers"]
    provider_summary = "\n".join([
        f"{p.upper()}: {d['account_count']} accounts, {d['cluster_count']} cluster(s)" for p, d in providers.items()
    ])
    return (
        f"Clusters: {clusters['running']} running, {clusters['stopped']} stopped, "
        f"{clusters['archived']} archived\n"
        f"Instances: {instances['count']}\n\n"
        f"Providers:\n{provider_summary}"
    )

@mcp.prompt()
def overview_prompt() -> list[base.Message]:
    overview = requests.get(f"{CLUSTERIQ_API_URL}/overview").json()
    summary = (
        f"Clusters: {overview['clusters']['running']} running, "
        f"{overview['clusters']['stopped']} stopped, "
        f"{overview['clusters']['archived']} archived.\n"
        f"Instances: {overview['instances']['count']}"
    )

    return [
        base.UserMessage("Analyze the current state:"),
        base.UserMessage(summary),
        base.AssistantMessage("Analysis result"),
    ]


if __name__ == "__main__":
    mcp.run()
