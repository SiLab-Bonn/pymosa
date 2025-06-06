from constellation.core.logging import setup_cli_logging
from constellation.core.satellite import SatelliteArgumentParser
from pymosa_satellite import Pymosa

def main(args=None):
    parser = SatelliteArgumentParser()
    args = vars(parser.parse_args(args))
    setup_cli_logging(args.pop("log_level"))
    s = Pymosa(**args)
    s.run_satellite()

if __name__ == "__main__":
    main()