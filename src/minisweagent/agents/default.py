"""Basic agent class. See https://mini-swe-agent.com/latest/advanced/control_flow/ for visual explanation."""

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from jinja2 import StrictUndefined, Template

from minisweagent import Environment, Model
from minisweagent.memory import HistoryManager, SessionMemory
from minisweagent.tools import REGISTRY as TOOL_REGISTRY
from minisweagent.tools import list_tool_specs


@dataclass
class AgentConfig:
    # The default settings are the bare minimum to run the agent. Take a look at the config files for improved settings.
    system_template: str = (
        "You are a helpful assistant that can do anything.\n"
        "If tools are available, you may call exactly one per step.\n"
        "{% if tool_specs %}Available tools:\n"
        "{% for t in tool_specs %}- {{t.name}}: {{t.description}} (parameters: {{t.parameters}})\n{% endfor %}{% endif %}"
    )
    instance_template: str = (
        "Your task: {{task}}. Provide EXACTLY ONE action in triple backticks.\n"
        "Choose one of:\n"
        "1) Bash command:\n"
        "```bash\n<your command>\n```\n"
        "2) Tool call:\n"
        '```tool\n{"name": "<tool_name>", "args": { ... }}\n```\n'
        "Prefer tools for reading/writing files or similar operations.\n"
        "To finish, ensure the first line of the resulting output is 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'."
    )
    timeout_template: str = (
        "The last command <command>{{action['action']}}</command> timed out and has been killed.\n"
        "The output of the command was:\n <output>\n{{output}}\n</output>\n"
        "Please try another command and make sure to avoid those requiring interactive input."
    )
    format_error_template: str = (
        "Please always provide EXACTLY ONE action in triple backticks: either a ```bash``` block or a ```tool``` block."
    )
    action_observation_template: str = "Observation: {{output}}"
    step_limit: int = 0
    cost_limit: float = 3.0
    enable_memory: bool = False
    memory_max_messages: int = 50
    memory_dir: str = ""
    memory_session_id: str = ""
    memory_load_session: bool = False


class NonTerminatingException(Exception):
    """Raised for conditions that can be handled by the agent."""


class FormatError(NonTerminatingException):
    """Raised when the LM's output is not in the expected format."""


class ExecutionTimeoutError(NonTerminatingException):
    """Raised when the action execution timed out."""


class TerminatingException(Exception):
    """Raised for conditions that terminate the agent."""


class Submitted(TerminatingException):
    """Raised when the LM declares that the agent has finished its task."""


class LimitsExceeded(TerminatingException):
    """Raised when the agent has reached its cost or step limit."""


class DefaultAgent:
    def __init__(self, model: Model, env: Environment, *, config_class: Callable = AgentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.messages: list[dict] = []
        self.model = model
        self.env = env
        self.tools = TOOL_REGISTRY
        self.extra_template_vars = {"tool_specs": list_tool_specs()}
        self.history_manager: HistoryManager | None = None
        self.session_memory: SessionMemory | None = None

        if self.config.enable_memory:
            self.history_manager = HistoryManager(max_messages=self.config.memory_max_messages)
            if self.config.memory_dir:
                self.session_memory = SessionMemory(
                    memory_dir=Path(self.config.memory_dir),
                    session_id=self.config.memory_session_id or None,
                )

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = asdict(self.config) | self.env.get_template_vars() | self.model.get_template_vars()
        return Template(template, undefined=StrictUndefined).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )

    def add_message(self, role: str, content: str, **kwargs):
        self.messages.append({"role": role, "content": content, **kwargs})

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message."""
        self.extra_template_vars |= {"task": task, **kwargs}
        self._initialize_messages()

        while True:
            try:
                self.step()
            except NonTerminatingException as e:
                self.add_message("user", str(e))
            except TerminatingException as e:
                self.add_message("user", str(e))
                if self.session_memory:
                    self.session_memory.save_session(self.messages, {"exit_status": type(e).__name__})
                return type(e).__name__, str(e)

    def _initialize_messages(self) -> None:
        self.messages = []
        if self.config.enable_memory and self.config.memory_load_session and self.session_memory:
            self.messages = self.session_memory.get_messages().copy()

        if not self.messages:
            self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))

    def step(self) -> dict:
        """Query the LM, execute the action, return the observation."""
        return self.get_observation(self.query())

    def query(self) -> dict:
        """Query the model and return the response."""
        if 0 < self.config.step_limit <= self.model.n_calls or 0 < self.config.cost_limit <= self.model.cost:
            raise LimitsExceeded()

        messages_to_send = self.messages
        if self.history_manager:
            messages_to_send = self.history_manager.compress_messages(self.messages)

        response = self.model.query(messages_to_send)
        self.add_message("assistant", **response)
        return response

    def get_observation(self, response: dict) -> dict:
        """Execute the action and return the observation."""
        output = self.execute_action(self.parse_action(response))
        self.add_message("user", self.render_template(self.config.action_observation_template, output=output))
        return output

    def parse_action(self, response: dict) -> dict:
        """Parse a single action: either a bash block or a tool block."""
        content = response["content"]
        tool_blocks = re.findall(r"```tool\n(.*?)\n```", content, re.DOTALL)
        bash_blocks = re.findall(r"```bash\n(.*?)\n```", content, re.DOTALL)

        if len(tool_blocks) + len(bash_blocks) != 1:
            raise FormatError(self.render_template(self.config.format_error_template, actions=[]))

        if tool_blocks:
            try:
                payload = json.loads(tool_blocks[0].strip())
                return {
                    "kind": "tool",
                    "tool_name": payload["name"],
                    "tool_args": payload.get("args", {}),
                    **response,
                }
            except Exception as e:
                raise FormatError(f"Invalid tool payload: {e}") from e

        return {"kind": "bash", "action": bash_blocks[0].strip(), **response}

    def execute_action(self, action: dict) -> dict:
        if action.get("kind") == "tool":
            return self._execute_tool_action(action)

        try:
            output = self.env.execute(action["action"])
        except subprocess.TimeoutExpired as e:
            output = e.output.decode("utf-8", errors="replace") if e.output else ""
            raise ExecutionTimeoutError(
                self.render_template(self.config.timeout_template, action=action, output=output)
            ) from e
        except TimeoutError as e:
            raise ExecutionTimeoutError(
                self.render_template(self.config.timeout_template, action=action, output="")
            ) from e
        self.has_finished(output)
        return output

    def _execute_tool_action(self, action: dict) -> dict:
        tool_name = action.get("tool_name", "")
        tool = self.tools.get(tool_name)
        if not tool:
            output = {"output": f"Unknown tool: {tool_name}", "returncode": 127}
            self.has_finished(output)
            return output
        try:
            try:
                output = tool(action.get("tool_args", {}), self.env)
            except TypeError:
                output = tool(action.get("tool_args", {}))
        except Exception as e:
            output = {"output": f"Tool '{tool_name}' error: {e}", "returncode": 1}
        self.has_finished(output)
        return output

    def has_finished(self, output: dict[str, str]):
        """Raise Submitted with final output if the agent has finished its task."""
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() in ["MINI_SWE_AGENT_FINAL_OUTPUT", "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"]:
            raise Submitted("".join(lines[1:]))
