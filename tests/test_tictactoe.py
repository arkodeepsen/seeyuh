import pytest
from unittest.mock import MagicMock

# Import the class under test
from engine.commands.fun import TicTacToeView

class TestTicTacToeView:
    @pytest.fixture
    def view(self):
        """Creates a TicTacToeView instance with a clean board."""
        # TicTacToeView.__init__ calls super().__init__() and creates buttons.
        # Since we mocked discord in conftest.py, this should work without side effects.
        return TicTacToeView()

    @pytest.mark.parametrize("row, winner", [
        (0, "X"), (1, "X"), (2, "X"),
        (0, "O"), (1, "O"), (2, "O"),
    ])
    def test_horizontal_wins(self, view, row, winner):
        """Test winning conditions for horizontal rows."""
        view.board = [["" for _ in range(3)] for _ in range(3)]
        view.board[row] = [winner, winner, winner]
        assert view.check_winner() == winner

    @pytest.mark.parametrize("col, winner", [
        (0, "X"), (1, "X"), (2, "X"),
        (0, "O"), (1, "O"), (2, "O"),
    ])
    def test_vertical_wins(self, view, col, winner):
        """Test winning conditions for vertical columns."""
        view.board = [["" for _ in range(3)] for _ in range(3)]
        for r in range(3):
            view.board[r][col] = winner
        assert view.check_winner() == winner

    @pytest.mark.parametrize("winner", ["X", "O"])
    def test_diagonal_wins(self, view, winner):
        """Test winning conditions for both diagonals."""
        # Main diagonal
        view.board = [["" for _ in range(3)] for _ in range(3)]
        view.board[0][0] = winner
        view.board[1][1] = winner
        view.board[2][2] = winner
        assert view.check_winner() == winner

        # Anti-diagonal
        view.board = [["" for _ in range(3)] for _ in range(3)]
        view.board[0][2] = winner
        view.board[1][1] = winner
        view.board[2][0] = winner
        assert view.check_winner() == winner

    def test_no_winner_empty(self, view):
        """Test that an empty board returns None."""
        view.board = [["" for _ in range(3)] for _ in range(3)]
        assert view.check_winner() is None

    def test_no_winner_partial(self, view):
        """Test that a partially filled board with no winner returns None."""
        view.board = [
            ["X", "O", "X"],
            ["O", "X", ""],
            ["", "", ""]
        ]
        assert view.check_winner() is None

    def test_no_winner_draw(self, view):
        """Test that a full board with no winner (draw) returns None."""
        view.board = [
            ["X", "O", "X"],
            ["X", "O", "O"],
            ["O", "X", "X"]
        ]
        assert view.check_winner() is None
