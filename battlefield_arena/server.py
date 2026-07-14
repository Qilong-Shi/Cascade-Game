from __future__ import annotations

import errno
import importlib
import json
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee.game import (  # noqa: E402
    Action,
    CascadeAction,
    Coord,
    Direction,
    EatAction,
    MoveAction,
    PlaceAction,
    PlayerColor,
)


ARENA_DIR = ROOT / "battlefield_arena"
BATTLEFIELD_DIR = ROOT / "battlefield_page"
HOST = os.environ.get("ARENA_HOST", "127.0.0.1")
PORT = int(os.environ.get("ARENA_PORT", "8787"))

DIRS = [Direction.Up, Direction.Down, Direction.Left, Direction.Right]
DIR_TO_INDEX = {
    Direction.Up: 0,
    Direction.Down: 1,
    Direction.Left: 2,
    Direction.Right: 3,
}

python_agents: dict[PlayerColor, object] = {}
player_specs: dict[PlayerColor, str] = {
    PlayerColor.RED: "agent:agent",
    PlayerColor.BLUE: "teacher",
}
agent_lock = Lock()

# added this file

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def action_from_index(index: int) -> Action:
    if index < 0 or index >= 832:
        raise ValueError(f"action index out of range: {index}")

    if index < 64:
        return PlaceAction(Coord(index // 8, index % 8))

    if index < 320:
        offset = index - 64
        square = offset // 4
        return MoveAction(Coord(square // 8, square % 8), DIRS[offset % 4])

    if index < 576:
        offset = index - 320
        square = offset // 4
        return EatAction(Coord(square // 8, square % 8), DIRS[offset % 4])

    offset = index - 576
    square = offset // 4
    return CascadeAction(Coord(square // 8, square % 8), DIRS[offset % 4])


def action_to_index(action: Action) -> int:
    if isinstance(action, PlaceAction):
        return action.coord.r * 8 + action.coord.c

    if isinstance(action, MoveAction):
        return 64 + (action.coord.r * 8 + action.coord.c) * 4 + DIR_TO_INDEX[action.direction]

    if isinstance(action, EatAction):
        return 320 + (action.coord.r * 8 + action.coord.c) * 4 + DIR_TO_INDEX[action.direction]

    if isinstance(action, CascadeAction):
        return 576 + (action.coord.r * 8 + action.coord.c) * 4 + DIR_TO_INDEX[action.direction]

    raise ValueError(f"unknown action: {action}")


def player_color(value: str) -> PlayerColor:
    value = value.lower()
    if value == "red":
        return PlayerColor.RED
    if value == "blue":
        return PlayerColor.BLUE
    raise ValueError(f"unknown color: {value}")


def color_name(color: PlayerColor) -> str:
    return color.name.lower()


def discover_agent_dirs() -> list[str]:
    agents = []
    for path in sorted(ROOT.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or not path.name.startswith("agent"):
            continue
        if (path / "program.py").is_file():
            agents.append(path.name)
    return agents


def load_agent(agent_dir: str, color: PlayerColor) -> object:
    if agent_dir not in discover_agent_dirs():
        raise ValueError(f"unknown agent folder: {agent_dir}")

    importlib.invalidate_caches()
    module_name = f"{agent_dir}.program"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    agent_class = getattr(module, "Agent", None)
    if agent_class is None:
        raise ValueError(f"{agent_dir}.program does not define Agent")
    return agent_class(color)


def normalise_player_spec(value: object) -> str:
    spec = str(value)
    if spec in {"human", "teacher"}:
        return spec
    if spec.startswith("agent:"):
        agent_dir = spec.split(":", 1)[1]
        if agent_dir in discover_agent_dirs():
            return spec
    raise ValueError(f"unknown player: {spec}")


def player_payload() -> dict:
    agents = [{"id": f"agent:{name}", "label": name} for name in discover_agent_dirs()]
    return {
        "ok": True,
        "players": [
            {"id": "human", "label": "Human"},
            {"id": "teacher", "label": "Teacher"},
            *agents,
        ],
        "current": {
            "red": player_specs[PlayerColor.RED],
            "blue": player_specs[PlayerColor.BLUE],
        },
    }


class ArenaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])

        if path == "/api/players":
            self.send_json(player_payload())
            return

        if path in {"", "/"}:
            self.serve_file(ARENA_DIR / "index.html")
            return

        if path.startswith("/az/"):
            self.serve_file(BATTLEFIELD_DIR / path.lstrip("/"))
            return

        self.serve_file(ARENA_DIR / path.lstrip("/"))

    def do_POST(self) -> None:
        try:
            payload = self.read_json()

            if self.path == "/api/new":
                self.handle_new_game(payload)
                return

            if self.path == "/api/notify":
                self.handle_notify(payload)
                return

            if self.path == "/api/agent_action":
                self.handle_agent_action(payload)
                return

            self.send_json({"ok": False, "error": "not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_new_game(self, payload: dict) -> None:
        global player_specs, python_agents

        players = payload.get("players", {})
        red_spec = normalise_player_spec(players.get("red", player_specs[PlayerColor.RED]))
        blue_spec = normalise_player_spec(players.get("blue", player_specs[PlayerColor.BLUE]))
        next_specs = {
            PlayerColor.RED: red_spec,
            PlayerColor.BLUE: blue_spec,
        }

        next_agents: dict[PlayerColor, object] = {}
        for color, spec in next_specs.items():
            if spec.startswith("agent:"):
                next_agents[color] = load_agent(spec.split(":", 1)[1], color)

        with agent_lock:
            player_specs = next_specs
            python_agents = next_agents

        self.send_json({
            "ok": True,
            "players": {color_name(color): spec for color, spec in player_specs.items()},
            "agents": {color_name(color): type(agent).__name__ for color, agent in python_agents.items()},
        })

    def handle_notify(self, payload: dict) -> None:
        color = player_color(str(payload["color"]))
        action = action_from_index(int(payload["action"]))

        with agent_lock:
            for agent in python_agents.values():
                agent.update(color, action)

        self.send_json({"ok": True})

    def handle_agent_action(self, payload: dict) -> None:
        color = player_color(str(payload["color"]))

        with agent_lock:
            spec = player_specs.get(color)
            if spec is None or not spec.startswith("agent:"):
                raise RuntimeError(f"{color_name(color)} is not a Python agent")
            agent = python_agents.get(color)
            if agent is None:
                raise RuntimeError(f"{color_name(color)} agent is not initialised")

            started = time.perf_counter()
            action = agent.action()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            index = action_to_index(action)

        self.send_json({
            "ok": True,
            "action": index,
            "text": str(action),
            "ms": elapsed_ms,
        })

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[arena] {self.address_string()} - {format % args}")


def bind_server() -> tuple[ReusableThreadingHTTPServer, int]:
    for port in range(PORT, PORT + 20):
        try:
            return ReusableThreadingHTTPServer((HOST, port), ArenaHandler), port
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    raise RuntimeError(f"no free port found from {PORT} to {PORT + 19}")


def main() -> None:
    server, port = bind_server()
    print(f"Arena running at http://{HOST}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
