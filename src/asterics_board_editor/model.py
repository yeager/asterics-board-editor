"""Data model for AAC boards and cells."""

import json
import uuid
import zipfile
import io
import gettext

_ = gettext.gettext


def new_id():
    return str(uuid.uuid4())


class CellAction:
    """Action triggered when a cell is activated."""
    SPEAK = "speak"
    NAVIGATE = "navigate"

    def __init__(self, action_type=None, value=""):
        self.action_type = action_type or self.SPEAK
        self.value = value

    def to_dict(self):
        return {"type": self.action_type, "value": self.value}

    @classmethod
    def from_dict(cls, data):
        return cls(
            action_type=data.get("type", cls.SPEAK),
            value=data.get("value", ""),
        )


class Cell:
    """A single cell in a communication board."""

    def __init__(self, label="", image_url="", bg_color="#FFFFFF", action=None, cell_id=None):
        self.id = cell_id or new_id()
        self.label = label
        self.image_url = image_url
        self.bg_color = bg_color
        self.action = action or CellAction()

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "image_url": self.image_url,
            "bg_color": self.bg_color,
            "action": self.action.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            label=data.get("label", ""),
            image_url=data.get("image_url", ""),
            bg_color=data.get("bg_color", "#FFFFFF"),
            action=CellAction.from_dict(data.get("action", {})),
            cell_id=data.get("id"),
        )


class Board:
    """A communication board containing cells in a grid."""

    def __init__(self, name="", rows=3, columns=4, board_id=None):
        self.id = board_id or new_id()
        self.name = name
        self.rows = rows
        self.columns = columns
        self.cells = []  # flat list, indexed row-major: row * columns + col

    def ensure_cells(self):
        """Ensure we have enough cells for the grid."""
        needed = self.rows * self.columns
        while len(self.cells) < needed:
            self.cells.append(None)
        self.cells = self.cells[:needed]

    def get_cell(self, row, col):
        idx = row * self.columns + col
        if 0 <= idx < len(self.cells):
            return self.cells[idx]
        return None

    def set_cell(self, row, col, cell):
        self.ensure_cells()
        idx = row * self.columns + col
        if 0 <= idx < len(self.cells):
            self.cells[idx] = cell

    def to_dict(self):
        self.ensure_cells()
        return {
            "id": self.id,
            "name": self.name,
            "rows": self.rows,
            "columns": self.columns,
            "cells": [c.to_dict() if c else None for c in self.cells],
        }

    @classmethod
    def from_dict(cls, data):
        board = cls(
            name=data.get("name", ""),
            rows=data.get("rows", 3),
            columns=data.get("columns", 4),
            board_id=data.get("id"),
        )
        board.cells = [
            Cell.from_dict(c) if c else None
            for c in data.get("cells", [])
        ]
        board.ensure_cells()
        return board


class Project:
    """A collection of boards (multi-board AAC project)."""

    def __init__(self):
        self.boards = []
        self.home_board_id = None

    @property
    def home_board(self):
        if self.home_board_id:
            for b in self.boards:
                if b.id == self.home_board_id:
                    return b
        return self.boards[0] if self.boards else None

    def add_board(self, board):
        self.boards.append(board)
        if not self.home_board_id:
            self.home_board_id = board.id

    def get_board_by_id(self, board_id):
        for b in self.boards:
            if b.id == board_id:
                return b
        return None

    def to_dict(self):
        return {
            "format": "asterics-board-editor",
            "version": 1,
            "home_board_id": self.home_board_id,
            "boards": [b.to_dict() for b in self.boards],
        }

    @classmethod
    def from_dict(cls, data):
        proj = cls()
        proj.home_board_id = data.get("home_board_id")
        for bd in data.get("boards", []):
            proj.boards.append(Board.from_dict(bd))
        return proj

    def save_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def export_grd(self, path):
        """Export as AsTeRICS Grid .grd format (zip of JSON)."""
        grd_data = self._to_asterics_format()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("grids.json", json.dumps(grd_data, indent=2, ensure_ascii=False))

    @classmethod
    def import_grd(cls, path):
        """Import from AsTeRICS Grid .grd format."""
        with zipfile.ZipFile(path, "r") as zf:
            with zf.open("grids.json") as f:
                grd_data = json.load(f)
        return cls._from_asterics_format(grd_data)

    def _to_asterics_format(self):
        """Convert to AsTeRICS Grid JSON structure."""
        grids = []
        for board in self.boards:
            board.ensure_cells()
            grid_elements = []
            for i, cell in enumerate(board.cells):
                if cell is None:
                    continue
                row = i // board.columns
                col = i % board.columns
                elem = {
                    "id": cell.id,
                    "label": {"en": cell.label} if cell.label else {},
                    "x": col,
                    "y": row,
                    "width": 1,
                    "height": 1,
                }
                if cell.image_url:
                    elem["image"] = {"url": cell.image_url}
                if cell.bg_color and cell.bg_color != "#FFFFFF":
                    elem["backgroundColor"] = cell.bg_color

                actions = []
                if cell.action.action_type == CellAction.SPEAK:
                    actions.append({
                        "type": "GridActionSpeak",
                        "speakLanguage": "",
                        "speakText": cell.action.value or cell.label,
                    })
                elif cell.action.action_type == CellAction.NAVIGATE:
                    actions.append({
                        "type": "GridActionNavigate",
                        "toGridId": cell.action.value,
                    })
                if actions:
                    elem["actions"] = actions

                grid_elements.append(elem)

            grids.append({
                "id": board.id,
                "label": {"en": board.name} if board.name else {},
                "rowCount": board.rows,
                "columnCount": board.columns,
                "gridElements": grid_elements,
            })

        return {
            "format": "asterics-erdi-grid",
            "modelVersion": "5",
            "grids": grids,
            "metadata": {
                "homeGridId": self.home_board_id,
            },
        }

    @classmethod
    def _from_asterics_format(cls, data):
        """Convert from AsTeRICS Grid JSON structure."""
        proj = cls()
        metadata = data.get("metadata", {})
        proj.home_board_id = metadata.get("homeGridId")

        for grid in data.get("grids", []):
            board = Board(
                name=_get_label(grid.get("label", {})),
                rows=grid.get("rowCount", 3),
                columns=grid.get("columnCount", 4),
                board_id=grid.get("id"),
            )
            board.ensure_cells()

            for elem in grid.get("gridElements", []):
                x = elem.get("x", 0)
                y = elem.get("y", 0)
                label = _get_label(elem.get("label", {}))
                image_url = ""
                img_data = elem.get("image", {})
                if img_data:
                    image_url = img_data.get("url", "")
                bg_color = elem.get("backgroundColor", "#FFFFFF")

                action = CellAction()
                for act in elem.get("actions", []):
                    if act.get("type") == "GridActionSpeak":
                        action = CellAction(CellAction.SPEAK, act.get("speakText", label))
                    elif act.get("type") == "GridActionNavigate":
                        action = CellAction(CellAction.NAVIGATE, act.get("toGridId", ""))

                cell = Cell(
                    label=label,
                    image_url=image_url,
                    bg_color=bg_color,
                    action=action,
                    cell_id=elem.get("id"),
                )
                board.set_cell(y, x, cell)

            proj.add_board(board)

        return proj


def _get_label(label_dict):
    """Get best label from multilingual dict."""
    if not label_dict:
        return ""
    if isinstance(label_dict, str):
        return label_dict
    for lang in ["en", "sv", "de", "es", "fr"]:
        if lang in label_dict:
            return label_dict[lang]
    vals = list(label_dict.values())
    return vals[0] if vals else ""
