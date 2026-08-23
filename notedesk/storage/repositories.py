from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from notedesk.models.state import RunState


class RunRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def upsert(self, run_state: RunState) -> None:
        payload = json.dumps(run_state.model_dump(mode="json"))
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO runs (run_id, session_id, goal, status, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    goal = excluded.goal,
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (
                    run_state.run_id,
                    run_state.session_id,
                    run_state.goal,
                    run_state.status.value,
                    payload,
                ),
            )
            connection.commit()

    def get(self, run_id: str) -> RunState:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT payload_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            raise KeyError(run_id)

        return RunState.model_validate_json(row[0])
