import pytest
from conftest import run


def test_no_command_shows_usage(capsys):
    with pytest.raises(SystemExit) as exit:
        run()
    assert exit.value.code == 2
    assert "COMMAND" in capsys.readouterr().err


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit):
        run("--help")
    out = capsys.readouterr().out
    for command in ("assignment", "hand-in", "delete", "outcomes", "feedback"):
        assert command in out


@pytest.mark.parametrize(
    "argv",
    [
        ["hand-in", "--course", "CMK", "--name", "x"],
        ["hand-in", "--course", "CMK", "--name", "x", "--doc", "/x", "--publish"],
        ["delete", "12", "--name", "Plan"],
    ],
)
def test_options_are_checked_by_the_parser(argv, canvas):
    with pytest.raises(SystemExit) as exit:
        run(*argv)
    assert exit.value.code == 2
    assert not canvas.calls
