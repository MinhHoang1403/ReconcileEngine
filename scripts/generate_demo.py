"""Generate the committed synthetic demo feeds and isolated evaluation truth."""

import argparse
from pathlib import Path

from smartrecon.generation import generate_vnd_demo, write_demo_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("data/demo/vn_synthetic_demo"))
    args = parser.parse_args()

    bundle = generate_vnd_demo(seed=args.seed, order_count=args.orders)
    for name, path in write_demo_bundle(bundle, args.output).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
