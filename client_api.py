import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters, stdio_client
from pydantic import BaseModel

from config import LLM_API_URL, LLM_MODEL_NAME
from logger import setup_logging

setup_logging()
log = logging.getLogger(__name__)

app = FastAPI()


class ChatRequest(BaseModel):
    query: str


load_dotenv()


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: List[Any] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        log.debug("Closing MCPClient resources...")
        await self.exit_stack.aclose()
        log.debug("MCPClient resources closed.")

    async def connect_to_server(self, server_script_path: str) -> List[Any]:
        log.debug("connect_to_server() called")

        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        log.debug(f"Launching MCP subprocess: {command} {server_script_path}")
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport

        log.debug("Creating session...")
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        log.debug("Initializing session...")
        await self.session.initialize()
        log.debug("Session initialized")

        response = await self.session.list_tools()

        self.tools = response.tools if hasattr(response, "tools") else []
        log.info(f"Tools loaded: {[tool.name for tool in self.tools]}")
        return self.tools


async def send_to_llm(formatted_messages: list[dict]) -> str:
    url = f"{LLM_API_URL}/v1/chat/completions"
    data = {
        "model": LLM_MODEL_NAME,
        "messages": formatted_messages,
        # TODO. Configure if needed
        "temperature": 0.1,
    }
    timeout_seconds = 120.0

    # PROVIDER_API_KEY = os.getenv("EXTERNAL_LLM_API_KEY")
    # headers = { "Authorization": f"Bearer {PROVIDER_API_KEY}" } if PROVIDER_API_KEY else {}
    headers = {}

    async with httpx.AsyncClient() as client:
        try:
            log.info(
                f"Calling LLM API (model: {LLM_MODEL_NAME}), timeout set to {timeout_seconds}s..."
            )
            response = await client.post(
                url, headers=headers, json=data, timeout=timeout_seconds
            )
            log.info("LLM API response received.")
            response.raise_for_status()
            result = response.json()
            log.debug(f"LLM raw response: {json.dumps(result, indent=2)}")

            if not result.get("choices") or not result["choices"][0].get("message"):
                log.error("LLM response missing expected structure.")
                raise ValueError("LLM response missing expected structure.")

            content = result["choices"][0]["message"]["content"]

            content = content if content is not None else ""
            log.info("LLM response content received.")
            return content.strip()

        except httpx.ReadTimeout:
            log.error(
                f"LLM API call timed out after {timeout_seconds} seconds.",
                exc_info=True,
            )
            raise Exception(f"LLM timed out after {timeout_seconds} seconds") from None
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            log.error(
                f"LLM API Error: Status {e.response.status_code} - {error_body}",
                exc_info=True,
            )
            raise Exception(
                f"LLM API Error: {e.response.status_code} - {error_body}"
            ) from e
        except Exception as e:
            log.error(f"Error during LLM call: {e}", exc_info=True)
            raise Exception(f"Error communicating with LLM: {str(e)}") from e


@app.post("/chat")
async def chat(request_body: ChatRequest):
    user_query_text = request_body.query
    log.info(f"/chat called with query: '{user_query_text}'")
    async with MCPClient() as mcp:
        try:
            tools_list = await mcp.connect_to_server("server.py")
            log.info(f"MCP connected, received {len(tools_list)} tools.")

            if not mcp.session:
                log.error("Failed to establish MCP session after connect_to_server.")

                raise HTTPException(
                    status_code=503,
                    detail="Error: Could not establish connection with backend agent.",
                )

            tools_prompt_description = "Available tools:\n"
            if tools_list:
                for tool in tools_list:
                    name = getattr(tool, "name", "Unnamed Tool")
                    description = getattr(tool, "description", "No description.")
                    tools_prompt_description += (
                        f"- Name: {name}\n  Description: {description}\n"
                    )
                    # TODO: Add parameter formatting when tools have parameters
            else:
                tools_prompt_description = "No tools are currently available.\n"

            system_prompt = f"""You are a helpful assistant specialized in answering questions about cloud inventory using the tools listed below.

            Your responsibilities:
            - Understand the user's request.
            - Use the available tools to retrieve relevant data.
            - Present a clear and accurate final answer.
            
            Guidelines:
            1. Carefully analyze the user's question and context.
            2. Check the 'Available tools' section. If a tool can provide the required data, go to step 3. Otherwise, answer based on context or explain that the information is unavailable.
            3. **To use a tool**, reply with a single-line JSON object only. Example:
               {{"tool_name": "tool_name_here", "arguments": {{"arg1": "value1", ...}}}}
               Do NOT include any other text.
            4. After the tool returns a result (from a message with role: 'tool'), use that result to compose a concise, final answer for the user.
            5. After receiving tool results, use them to answer the user naturally and concisely. Choose a format that matches the user’s intent:
            - Use tables for listings and comparisons.
            - Use natural sentences for specific facts or single results.
            - Use summaries or groupings if the user asked for trends or categories.
     
            {tools_prompt_description}
            
            **CRITICAL:** Only output the JSON tool call structure when you need to use a tool. For all other responses, including the final answer after getting tool results, use natural language."""

            messages: List[Dict[str, str]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query_text},
            ]

            max_loops = 5
            for i in range(max_loops):
                log.debug(f"\n--- Agent Loop Iteration {i + 1} ---")
                log.debug(">>> Preparing to call LLM...")
                log.debug(f"Messages to be sent: {json.dumps(messages, indent=2)}")

                try:
                    llm_response_content = await send_to_llm(messages)
                    log.debug(
                        f"<<< LLM call successful. Response received: '{llm_response_content}'"
                    )
                except Exception as llm_error:
                    log.error(
                        f"LLM call failed during iteration {i + 1}: {llm_error}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=f"Error communicating with Language Model: {str(llm_error)}",
                    )
                tool_call_request = None
                try:
                    parsed_response = json.loads(llm_response_content.strip())
                    if (
                        isinstance(parsed_response, dict)
                        and "tool_name" in parsed_response
                        and "arguments" in parsed_response
                        and isinstance(parsed_response["arguments"], dict)
                    ):
                        tool_call_request = parsed_response
                        log.info("LLM requested a tool call.")
                    else:
                        log.debug(
                            "LLM response is JSON but not a valid tool call structure."
                        )
                except json.JSONDecodeError:
                    log.debug("LLM response is not JSON, treating as final answer.")
                except Exception as parse_error:
                    log.warning(
                        f"Error parsing LLM response: {parse_error}. Treating as final answer."
                    )

                if tool_call_request:
                    tool_name = tool_call_request.get("tool_name", "Unknown Tool")
                    arguments = tool_call_request.get("arguments", {})

                    messages.append(
                        {"role": "assistant", "content": llm_response_content}
                    )
                    log.info(
                        f"Executing tool: '{tool_name}' with arguments: {arguments}"
                    )

                    tool_message_content = f"Error: Tool '{tool_name}' did not produce a interpretable result."

                    try:
                        tool_result = await mcp.session.call_tool(
                            tool_name, arguments=arguments
                        )

                        if hasattr(tool_result, "isError") and tool_result.isError:
                            error_text = (
                                f"Tool Error: Execution failed for '{tool_name}'."
                            )
                            if hasattr(tool_result, "content") and tool_result.content:
                                content_obj = tool_result.content

                                if (
                                    isinstance(content_obj, list)
                                    and len(content_obj) > 0
                                ):
                                    first_content = content_obj[0]
                                    if hasattr(first_content, "text"):
                                        error_text = f"Tool Error: {first_content.text}"
                                elif hasattr(content_obj, "text"):
                                    error_text = f"Tool Error: {content_obj.text}"
                            tool_message_content = error_text
                            log.error(
                                f"Tool execution returned error: {tool_message_content}"
                            )
                        else:
                            log.info(
                                f"Tool '{tool_name}' executed successfully (returned non-error)."
                            )
                            if hasattr(tool_result, "content") and tool_result.content:
                                content_obj = tool_result.content

                                if (
                                    isinstance(content_obj, list)
                                    and len(content_obj) > 0
                                ):
                                    first_content = content_obj[0]
                                    if hasattr(first_content, "text"):
                                        tool_message_content = first_content.text
                                        log.debug(
                                            f"Extracted text from TextContent list: {tool_message_content}"
                                        )
                                    else:
                                        log.warning(
                                            "Tool result content list item has no 'text' attribute."
                                        )
                                        tool_message_content = str(content_obj)
                                elif hasattr(content_obj, "text"):
                                    tool_message_content = content_obj.text
                                    log.debug(
                                        f"Extracted text from TextContent object: {tool_message_content}"
                                    )
                                else:
                                    log.warning(
                                        f"Tool result content is unexpected type: {type(content_obj)}. Stringifying."
                                    )
                                    tool_message_content = str(content_obj)

                            elif tool_result is None or not hasattr(
                                tool_result, "content"
                            ):
                                tool_message_content = f"Tool '{tool_name}' executed successfully with no specific content returned."
                            else:
                                log.warning(
                                    f"Tool result has unexpected structure: {tool_result}. Stringifying."
                                )
                                tool_message_content = str(tool_result)

                    except Exception as tool_exception:
                        error_msg = f"Exception during mcp.session.call_tool '{tool_name}': {str(tool_exception)}"
                        log.error(error_msg, exc_info=True)
                        tool_message_content = error_msg

                    messages.append({"role": "tool", "content": tool_message_content})

                else:
                    log.info("LLM provided final answer.")

                    return {"response": llm_response_content.strip()}

            log.warning(f"Maximum agent loops ({max_loops}) reached.")

            last_assistant_message = "Processing stopped after maximum attempts."
            for msg in reversed(messages):
                if msg["role"] == "assistant":
                    try:
                        parsed_last = json.loads(msg["content"].strip())
                        if isinstance(parsed_last, dict) and "tool_name" in parsed_last:
                            last_assistant_message = f"Processing stopped - LLM was still trying to call tool '{parsed_last['tool_name']}'."
                        else:
                            last_assistant_message = msg["content"].strip()

                    except json.JSONDecodeError:
                        last_assistant_message = msg["content"].strip()
                    break

            return {
                "response": f"Max loops reached. Last response: {last_assistant_message}"
            }

        except HTTPException:
            raise
        except Exception as e:
            log.error(
                f"An unexpected error occurred in /chat handler: {e}", exc_info=True
            )

            raise HTTPException(
                status_code=500, detail=f"An unexpected server error occurred: {str(e)}"
            )
