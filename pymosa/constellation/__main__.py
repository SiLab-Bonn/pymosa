from constellation.core.logging import setup_cli_logging
from constellation.core.satellite import SatelliteArgumentParser
from pymosa.constellation.pymosa_satellite import Pymosa

def main(args=None):
    parser = SatelliteArgumentParser()
    args = vars(parser.parse_args(args))
    setup_cli_logging(args.pop("level"))
    s = Pymosa(**args)
    s.run_satellite()

if __name__ == "__main__":
    main()