"""A tiny task board for exercising TERN's editor signals.

It is intentionally ordinary code: open it, move around, make a few edits,
and let TERN observe the shape of the session without reading the source.
"""

from dataclasses import dataclass
from time import sleep


@dataclass(frozen=True)
class Task:
    title: str
    minutes: int
    energy: int
    blocked: bool = False


TASKS = [
    Task("Map the study flow", 25, 2),
    Task("Read the capture contract", 15, 1),
    Task("Fix the noisy retry", 35, 4, blocked=True),
    Task("Write the handoff note", 20, 2),
]


def score_task(task: Task) -> float:
    """Return a higher score for urgent, low-effort work."""
    urgency = max(1, 60 - task.minutes)
    friction = 2 if task.blocked else 0
    return (urgency / max(task.energy, 1)) - friction


def prioritize_tasks(tasks: list[Task]) -> list[Task]:
    """Sort tasks for a focused afternoon.

    This is intentionally a little more verbose than it needs to be. It gives
    the stuck detector a friendly region to watch while you try the extension.
    """
    ranked: list[tuple[float, Task]] = []

    for task in tasks:
        # Try moving the caret around this block without editing to see the
        # inline stuck prompt after the demo threshold has elapsed.
        score = score_task(task)
        if task.blocked:
            score -= 1
        ranked.append((score, task))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [task for _, task in ranked]


def render_board(tasks: list[Task]) -> str:
    lines = ["TERN lab — today's queue", "=" * 26]
    for index, task in enumerate(tasks, start=1):
        state = "blocked" if task.blocked else "ready"
        lines.append(f"{index}. {task.title:<28} {state:>7}")
    return "\n".join(lines)


def focus_break(seconds: int = 1) -> None:
    """Model a short pause between two pieces of work."""
    sleep(seconds)


def main() -> None:
    queue = prioritize_tasks(TASKS)
    print(render_board(queue))
    focus_break()
    print("\nNext up:", queue[0].title)


if __name__ == "__main__":
    main()
