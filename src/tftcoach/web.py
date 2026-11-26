from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .models import GameContext, UnitState
from .recommender import Recommender


app = FastAPI(title="TFT Coach", version="0.2.0")


class UnitInput(BaseModel):
    name: str
    cost: int = Field(ge=1, le=5)
    star: int = Field(default=1, ge=1, le=3)
    items: list[str] = Field(default_factory=list)
    owned_count: int = Field(default=0, ge=0)


class RecommendationInput(BaseModel):
    stage: str = "4-5"
    round_type: str = "pvplive"
    health: int = Field(default=50, ge=0, le=100)
    gold: int = Field(default=30, ge=0)
    level: int = Field(default=7, ge=1, le=10)
    board: list[str] = Field(default_factory=list)
    opponents: list[str] = Field(default_factory=list)
    units: list[UnitInput] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


@app.post("/api/recommend")
def recommend(input_data: RecommendationInput):
    units = tuple(
        UnitState(
            name=item.name,
            cost=item.cost,
            star=item.star,
            items=tuple(item.items),
            owned_count=item.owned_count,
        )
        for item in input_data.units
    )
    context = GameContext(
        stage=input_data.stage,
        round_type=input_data.round_type,
        health=input_data.health,
        gold=input_data.gold,
        level=input_data.level,
        board=tuple(input_data.board),
        opponents=tuple(input_data.opponents),
        units=units,
        items=tuple(input_data.items),
    )

    recommendations = Recommender().recommend(context)
    return {
        "context": {
            "stage": context.stage,
            "health": context.health,
            "gold": context.gold,
            "level": context.level,
        },
        "recommendations": [
            {
                "action": item.action,
                "score": item.score,
                "sample_count": item.sample_count,
                "confidence": item.confidence,
                "reason": item.reason,
                "execution_order": item.execution_order,
                "prerequisites": list(item.prerequisites),
            }
            for item in recommendations[:12]
        ],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    template = Path(__file__).with_name("web_template.html")
    return HTMLResponse(template.read_text(encoding="utf-8"))
