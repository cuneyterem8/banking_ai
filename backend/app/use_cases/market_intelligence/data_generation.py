from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.data_paths import get_use_case_data_dir

USE_CASE_SLUG = "market-intelligence"
GENERATION_SEED = 9909
NEWS_COUNT = 180
RATE_DAY_COUNT = 180
COMPETITOR_RATE_COUNT = 80
CALENDAR_EVENT_COUNT = 36
EVALUATION_CASE_COUNT = 8
REFERENCE_DATE = date(2026, 6, 1)

TOPICS = [
    "rates",
    "deposits",
    "credit",
    "regulation",
    "payments",
    "fraud",
    "aml",
    "consumer_sentiment",
]
SECTORS = ["Retail Banking", "Treasury", "Consumer Credit", "Compliance", "Payments", "Small Business"]
IMPACT_AREAS = [
    "deposit_pricing",
    "loan_demand",
    "credit_risk",
    "liquidity_cash_demand",
    "aml_fraud_compliance",
    "customer_communications",
    "market_opportunity",
]
SENTIMENTS = ["positive", "negative", "mixed", "watch"]
URGENCIES = ["low", "medium", "high"]


def market_data_root() -> Path:
    return get_use_case_data_dir(USE_CASE_SLUG)


def market_raw_root() -> Path:
    return market_data_root() / "raw"


def metadata_path() -> Path:
    return market_data_root() / "metadata.json"


def ground_truth_path() -> Path:
    return market_data_root() / "ground_truth.json"


def news_path() -> Path:
    return market_raw_root() / "news" / "synthetic_market_news.json"


def rates_path() -> Path:
    return market_raw_root() / "rates" / "rates_timeseries.csv"


def competitors_path() -> Path:
    return market_raw_root() / "competitors" / "competitor_product_rates.xlsx"


def calendar_path() -> Path:
    return market_raw_root() / "calendar" / "economic_calendar.csv"


def snapshot_pdf_path() -> Path:
    return market_raw_root() / "research" / "market_snapshot.pdf"


def taxonomy_path() -> Path:
    return market_raw_root() / "taxonomy" / "topics.json"


def evaluation_cases_path() -> Path:
    return market_raw_root() / "evaluation" / "research_brief_cases.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0]) if rows else ["status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(path: Path, sheet_name: str, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    headers = list(rows[0]) if rows else ["status"]
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    workbook.save(path)
    workbook.close()


def _write_pdf(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 54
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(54, y, title)
    y -= 28
    pdf.setFont("Helvetica", 10)
    for line in lines:
        if y < 64:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 54
        pdf.drawString(54, y, line[:112])
        y -= 15
    pdf.save()


def _news_articles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    publishers = ["Synthetic Markets Daily", "Banking Signal Wire", "Public Finance Observer", "Consumer Credit Brief"]
    for index in range(1, NEWS_COUNT + 1):
        topic = TOPICS[index % len(TOPICS)]
        sector = SECTORS[index % len(SECTORS)]
        impact_area = IMPACT_AREAS[index % len(IMPACT_AREAS)]
        sentiment = SENTIMENTS[index % len(SENTIMENTS)]
        urgency = URGENCIES[index % len(URGENCIES)]
        published_at = REFERENCE_DATE - timedelta(days=index % 45)
        rows.append(
            {
                "article_id": f"MI-NEWS-{index:04d}",
                "title": f"Synthetic {topic.replace('_', ' ').title()} Signal {index:03d}",
                "publisher": publishers[index % len(publishers)],
                "published_at": published_at.isoformat(),
                "topic": topic,
                "sector": sector,
                "impact_area": impact_area,
                "sentiment": sentiment,
                "urgency": urgency,
                "summary": (
                    f"Synthetic public-style report on {topic.replace('_', ' ')} for {sector}. "
                    f"The signal is {sentiment} with {urgency} urgency and may affect {impact_area.replace('_', ' ')}."
                ),
                "url": f"https://synthetic.example/market-intelligence/{index:04d}",
            }
        )
    return rows


def _rate_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(RATE_DAY_COUNT):
        day = REFERENCE_DATE - timedelta(days=RATE_DAY_COUNT - index - 1)
        cycle = (index % 30) / 30
        rows.append(
            {
                "date": day.isoformat(),
                "fed_funds_rate": round(4.35 + cycle * 0.18 + (index % 7) * 0.004, 3),
                "treasury_10y": round(4.05 + cycle * 0.26 - (index % 5) * 0.006, 3),
                "mortgage_30y": round(6.55 + cycle * 0.35 + (index % 6) * 0.01, 3),
                "deposit_beta_index": round(0.42 + cycle * 0.08, 3),
                "usd_index": round(103.0 + cycle * 2.3 - (index % 11) * 0.05, 3),
                "inflation_expectation": round(2.35 + cycle * 0.18, 3),
            }
        )
    return rows


def _competitor_rates() -> list[dict[str, Any]]:
    products = [
        ("deposits", "High Yield Savings", 4.1, 0),
        ("deposits", "Business Money Market", 3.55, 10),
        ("lending", "Auto Loan", 7.4, 75),
        ("credit_card", "Rewards Card", 22.5, 95),
        ("mortgage", "Thirty Year Fixed", 6.8, 995),
        ("small_business", "Working Capital Line", 10.2, 150),
    ]
    rows: list[dict[str, Any]] = []
    for index in range(1, COMPETITOR_RATE_COUNT + 1):
        product_line, product_name, base_rate, base_fee = products[index % len(products)]
        rows.append(
            {
                "competitor_id": f"COMP-{index % 12 + 1:03d}",
                "competitor_name": f"Synthetic Bank {index % 12 + 1}",
                "product_line": product_line,
                "product_name": product_name,
                "rate": round(base_rate + (index % 9) * 0.07, 3),
                "fee": round(base_fee + (index % 4) * 12.5, 2),
                "region": "US",
                "effective_date": (REFERENCE_DATE - timedelta(days=index % 21)).isoformat(),
                "source_note": "Synthetic competitor snapshot for MVP testing.",
            }
        )
    return rows


def _calendar_events() -> list[dict[str, Any]]:
    event_types = ["central_bank", "inflation", "jobs", "housing", "regulatory", "consumer_credit"]
    rows: list[dict[str, Any]] = []
    for index in range(1, CALENDAR_EVENT_COUNT + 1):
        event_type = event_types[index % len(event_types)]
        rows.append(
            {
                "event_id": f"MI-CAL-{index:03d}",
                "event_date": (REFERENCE_DATE + timedelta(days=index * 3)).isoformat(),
                "event_type": event_type,
                "title": f"Synthetic {event_type.replace('_', ' ').title()} Event {index:02d}",
                "expected_impact": SENTIMENTS[index % len(SENTIMENTS)],
                "affected_areas": "|".join([IMPACT_AREAS[index % len(IMPACT_AREAS)], IMPACT_AREAS[(index + 2) % len(IMPACT_AREAS)]]),
            }
        )
    return rows


def _taxonomy() -> dict[str, Any]:
    return {
        "topics": TOPICS,
        "sectors": SECTORS,
        "impact_areas": IMPACT_AREAS,
        "directions": SENTIMENTS,
        "urgency_levels": URGENCIES,
        "product_lines": ["deposits", "lending", "credit_card", "mortgage", "small_business", "payments"],
    }


def _evaluation_cases() -> list[dict[str, Any]]:
    objectives = [
        "Summarize rate and deposit pricing pressure for US retail banking.",
        "Identify consumer credit risk signals from current public market information.",
        "Assess payment and fraud signals relevant to bank operations.",
        "Create a regulatory watch brief for banking compliance leaders.",
        "Find market opportunity signals for small business banking.",
        "Assess mortgage and housing market implications for bank lending.",
        "Summarize liquidity and treasury signals for branch cash planning.",
        "Create a daily executive brief across rates, credit, deposits, and regulation.",
    ]
    return [
        {
            "case_id": f"MI-CASE-{index:03d}",
            "objective": objective,
            "region": "US",
            "focus_areas": ["rates", "deposits", "credit", "regulation"] if index == 8 else [TOPICS[(index + offset) % len(TOPICS)] for offset in range(4)],
            "depth": "standard",
            "max_search_calls": 6,
            "use_live_web": True,
            "expected_impact_areas": [IMPACT_AREAS[index % len(IMPACT_AREAS)], IMPACT_AREAS[(index + 3) % len(IMPACT_AREAS)]],
        }
        for index, objective in enumerate(objectives, start=1)
    ]


def write_artifacts() -> dict[str, str]:
    random.seed(GENERATION_SEED)
    root = market_data_root()
    if root.exists():
        shutil.rmtree(root)
    market_raw_root().mkdir(parents=True, exist_ok=True)

    news = _news_articles()
    rates = _rate_records()
    competitors = _competitor_rates()
    calendar = _calendar_events()
    taxonomy = _taxonomy()
    cases = _evaluation_cases()

    _write_json(news_path(), news)
    _write_csv(rates_path(), rates)
    _write_xlsx(competitors_path(), "competitor_product_rates", competitors)
    _write_csv(calendar_path(), calendar)
    _write_json(taxonomy_path(), taxonomy)
    _write_json(evaluation_cases_path(), cases)
    _write_pdf(
        snapshot_pdf_path(),
        "Synthetic Banking Market Snapshot",
        [
            "This synthetic report summarizes market themes for banking research workflows.",
            "Deposit pricing pressure remains sensitive to rate expectations and competitor promotional behavior.",
            "Consumer credit risk signals are mixed, with attention on delinquency, household cash flow, and employment data.",
            "Payments, fraud, and AML operations should monitor regulatory announcements and transaction behavior changes.",
            "This document is synthetic and is not investment advice.",
        ],
    )

    ground_truth = {
        "generation_seed": GENERATION_SEED,
        "news_count": len(news),
        "rate_record_count": len(rates),
        "competitor_rate_count": len(competitors),
        "calendar_event_count": len(calendar),
        "evaluation_case_count": len(cases),
        "expected_topics": TOPICS,
        "expected_impact_areas": IMPACT_AREAS,
        "required_agents": [
            "Research Orchestrator",
            "Query Planner",
            "Search Scout",
            "Evidence Extractor",
            "Source Verifier",
            "Signal Scorer",
            "Executive Synthesizer",
            "Citation Reviewer",
        ],
    }
    _write_json(ground_truth_path(), ground_truth)

    artifact_paths = [
        news_path(),
        rates_path(),
        competitors_path(),
        calendar_path(),
        snapshot_pdf_path(),
        taxonomy_path(),
        evaluation_cases_path(),
        ground_truth_path(),
    ]
    metadata = {
        "generation_seed": GENERATION_SEED,
        "news_count": len(news),
        "rate_record_count": len(rates),
        "competitor_rate_count": len(competitors),
        "calendar_event_count": len(calendar),
        "evaluation_case_count": len(cases),
        "artifact_checksums": {
            str(path.resolve().relative_to(root.resolve())).replace("\\", "/"): _sha256(path)
            for path in artifact_paths
        },
    }
    _write_json(metadata_path(), metadata)
    artifact_paths.append(metadata_path())

    return {
        "raw_root": str(market_raw_root().resolve()),
        "news": str(news_path().resolve()),
        "rates": str(rates_path().resolve()),
        "competitors": str(competitors_path().resolve()),
        "calendar": str(calendar_path().resolve()),
        "snapshot_pdf": str(snapshot_pdf_path().resolve()),
        "taxonomy": str(taxonomy_path().resolve()),
        "evaluation_cases": str(evaluation_cases_path().resolve()),
        "ground_truth": str(ground_truth_path().resolve()),
        "metadata": str(metadata_path().resolve()),
    }
