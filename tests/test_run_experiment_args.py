"""Le pilote d'expérience expose --machines (reproduction ailleurs) et garde ses défauts."""
from bdflab.run_experiment import build_parser


def test_machines_option_and_defaults():
    a = build_parser().parse_args(["--exe", "x.exe"])
    assert a.machines == 1 and a.runs == 2
    assert build_parser().parse_args(["--exe", "x.exe", "--machines", "2"]).machines == 2
