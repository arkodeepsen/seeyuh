import pytest
from engine.commands.fun import TicTacToeView

class TestTicTacToeView:
    def test_is_board_full_empty(self):
        """Test is_board_full returns False for an empty board."""
        view = TicTacToeView()
        # Ensure the board is empty (it should be by default)
        view.board = [["" for _ in range(3)] for _ in range(3)]
        assert view.is_board_full() is False

    def test_is_board_full_partial(self):
        """Test is_board_full returns False for a partially filled board."""
        view = TicTacToeView()
        view.board = [
            ["X", "O", "X"],
            ["O", "X", ""],
            ["O", "X", "O"]
        ]
        assert view.is_board_full() is False

    def test_is_board_full_full(self):
        """Test is_board_full returns True for a full board."""
        view = TicTacToeView()
        view.board = [
            ["X", "O", "X"],
            ["O", "X", "O"],
            ["X", "O", "X"]
        ]
        assert view.is_board_full() is True

    def test_is_board_full_single_empty(self):
        """Test is_board_full returns False if even one cell is empty."""
        view = TicTacToeView()
        # Fill board except last cell
        view.board = [
            ["X", "O", "X"],
            ["O", "X", "O"],
            ["X", "O", ""]
        ]
        assert view.is_board_full() is False
