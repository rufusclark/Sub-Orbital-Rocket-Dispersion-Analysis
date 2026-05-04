import contextlib
import re
import sys
import time
import datetime


class ProgressBar:
    def __init__(self, tasks: int) -> None:
        self.tasks = tasks
        self.start_time = time.time()
        self.update(0)

    def update(self, tasks_completed: int) -> None:
        percent = tasks_completed/self.tasks
        elapsed = time.time() - self.start_time

        bar_width = 20
        filled = int(bar_width * percent)
        bar = "#" * filled + " " * (bar_width - filled)

        remaining = (elapsed / tasks_completed) * (
            self.tasks - tasks_completed) if tasks_completed else 0

        sys.stdout.write(
            f"\r[{bar}] {percent:.2%} (eta: {datetime.timedelta(seconds=int(remaining))})")
        sys.stdout.flush()

        if self.tasks == tasks_completed:
            sys.stdout.write(f"\n")
            sys.stdout.flush()


class RegexFilter:
    def __init__(self, pattern, stream):
        self.pattern = re.compile(pattern)
        self.stream = stream
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line += "\n"  # add the newline back
            if not self.pattern.match(line):
                self.stream.write(line)

    def flush(self):
        # Write any remaining text if it doesn't match
        if self.buffer and not self.pattern.match(self.buffer):
            self.stream.write(self.buffer)
        self.buffer = ""
        self.stream.flush()
