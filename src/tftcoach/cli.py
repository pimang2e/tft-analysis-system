import argparse

from .collector import DataDragonCollector
from .models import GameContext
from .recommender import Recommender


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tft-coach")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect official metadata")
    collect.add_argument("--locale", default="ko_KR")

    recommend = subparsers.add_parser("recommend", help="Recommend a situational action")
    recommend.add_argument("--stage", default="3-5")
    recommend.add_argument("--round-type", default="pvplive")
    recommend.add_argument("--health", type=int, default=50)
    recommend.add_argument("--gold", type=int, default=30)
    recommend.add_argument("--level", type=int, default=7)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "collect":
        result = DataDragonCollector(locale=args.locale).collect()
        print(
            f"수집 완료: {result['source']} {result['version']} "
            f"({result['locale']}, 챔피언 {result['champion_count']}개, "
            f"특성 {result['trait_count']}개, 증강 {result['augment_count']}개, "
            f"아이템 {result['item_count']}개)"
        )
        return

    context = GameContext(
        stage=args.stage,
        round_type=args.round_type,
        health=args.health,
        gold=args.gold,
        level=args.level,
    )
    recommendations = Recommender().recommend(context)

    print(f"상황: 스테이지 {context.stage}, 체력 {context.health}, 골드 {context.gold}, 레벨 {context.level}")
    for rank, item in enumerate(recommendations[:5], start=1):
        print(
            f"{rank}. {item.action} | 점수 {item.score:.3f} | "
            f"표본 {item.sample_count} | 신뢰도 {item.confidence} | {item.reason}"
        )


if __name__ == "__main__":
    main()
