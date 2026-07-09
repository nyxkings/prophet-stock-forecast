"""Database operations for saving optimisation results to Supabase."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from supabase import Client, create_client

from src.market_calendar import next_trading_day
from src.settings import SUPABASE_TABLE_NAME

logger = logging.getLogger(__name__)


def _load_project_env() -> None:
    """Load variables from project-root .env when not already in the environment."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_project_env()


def get_supabase_client() -> Client | None:
    """
    Create and return Supabase client from environment variables.

    Returns:
        Supabase client if credentials are available, None otherwise
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        logger.warning("Supabase credentials not found in environment variables")
        return None

    return create_client(url, key)


def _prediction_target_date(as_of: date) -> date:
    """Next US trading day after the optimisation as-of date."""
    return next_trading_day(as_of)


def save_results_to_supabase(result: dict[str, Any]) -> None:
    """
    Save optimisation results to Supabase database.

    Args:
        result: Dictionary containing optimisation results from run_optimisation()
            Expected keys: predictions, predicted_returns, weights
            Optional keys: current_prices, prediction_date

    Raises:
        ValueError: If Supabase client cannot be created or insertion fails
    """
    supabase = get_supabase_client()
    if supabase is None:
        raise ValueError(
            "Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY environment variables."
        )

    as_of_date = result.get("date")
    predictions = result.get("predictions", {})
    predicted_returns = result.get("predicted_returns", {})
    weights = result.get("weights", {})
    actual_prices_last_month = result.get("actual_prices_last_month", {})
    current_prices = result.get("current_prices", {})
    prediction_date = result.get("prediction_date")

    if not predictions:
        logger.warning("No predictions to save")
        return

    if prediction_date is None and as_of_date is not None:
        prediction_date = _prediction_target_date(as_of_date)

    # Prepare rows for insertion - one row per stock
    rows = []
    for ticker in predictions.keys():
        row = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "as_of_date": as_of_date.isoformat() if as_of_date else None,
            "ticker": ticker,
            "predicted_price": float(predictions.get(ticker, 0.0)),
            "predicted_return": float(predicted_returns.get(ticker, 0.0)),
            "actual_prices_last_month": json.dumps(actual_prices_last_month.get(ticker, [])),
            "portfolio_weight": float(weights.get(ticker, 0.0)),
            # Additive outcome fields (nullable until scored)
            "prediction_target_date": (
                prediction_date.isoformat()
                if isinstance(prediction_date, date)
                else (str(prediction_date) if prediction_date is not None else None)
            ),
            "current_price": (float(current_prices[ticker]) if ticker in current_prices else None),
            "actual_price": None,
            "actual_return": None,
            "price_error": None,
            "return_error": None,
            "scored_at": None,
        }
        rows.append(row)

    logger.info(f"Inserting {len(rows)} rows into Supabase...")
    try:
        (supabase.table(SUPABASE_TABLE_NAME).insert(rows).execute())
    except Exception as exc:
        # Soft rollback: if new columns are missing in remote schema, retry without them
        message = str(exc).lower()
        if "column" in message or "schema" in message or "pgrst" in message:
            logger.warning(
                "Insert with outcome columns failed (%s); retrying without additive fields. "
                "Run scripts/sql/add_outcome_columns.sql when ready.",
                exc,
            )
            legacy_rows = [
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "as_of_date": row["as_of_date"],
                    "ticker": row["ticker"],
                    "predicted_price": row["predicted_price"],
                    "predicted_return": row["predicted_return"],
                    "actual_prices_last_month": row["actual_prices_last_month"],
                    "portfolio_weight": row["portfolio_weight"],
                }
                for row in rows
            ]
            (supabase.table(SUPABASE_TABLE_NAME).insert(legacy_rows).execute())
        else:
            raise

    logger.info(f"Successfully saved {len(rows)} predictions to Supabase")


def _fetch_unscored_rows(supabase: Client, limit: int = 500) -> list[dict[str, Any]]:
    """Fetch recent rows that still need actual outcomes filled."""
    response = (
        supabase.table(SUPABASE_TABLE_NAME)
        .select(
            "id,as_of_date,ticker,predicted_price,predicted_return,current_price,"
            "prediction_target_date,actual_price,actual_prices_last_month"
        )
        .is_("actual_price", "null")
        .order("as_of_date", desc=True)
        .limit(limit)
        .execute()
    )
    data = response.data or []
    return [dict(row) for row in data]  # type: ignore[arg-type]


def _close_price_on_or_after(ticker: str, target: date) -> float | None:
    """Download a small window and return the first available close on/after target."""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance unavailable; cannot score outcomes")
        return None

    end = target + timedelta(days=5)
    try:
        frame = yf.download(
            ticker,
            start=target.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        logger.warning("Failed to download prices for %s: %s", ticker, exc)
        return None

    if frame is None or frame.empty or "Close" not in frame.columns:
        return None

    closes = frame["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[0])


def score_previous_predictions(lookback_days: int = 14) -> dict[str, Any]:
    """
    Fill actual outcomes for previously saved predictions (soft-fail friendly).

    Returns:
        Summary dict with counts. Never raises for network/data issues; logs instead.
        Raises ValueError only when Supabase credentials are missing.
    """
    supabase = get_supabase_client()
    if supabase is None:
        raise ValueError(
            "Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY environment variables."
        )

    summary: dict[str, Any] = {"attempted": 0, "updated": 0, "skipped": 0, "errors": 0}

    try:
        rows = _fetch_unscored_rows(supabase)
    except Exception as exc:
        logger.warning("Could not fetch unscored rows (schema may lack outcome columns): %s", exc)
        summary["errors"] = 1
        return summary

    cutoff = date.today() - timedelta(days=lookback_days)
    for row in rows:
        summary["attempted"] += 1
        try:
            as_of_raw = row.get("as_of_date")
            if not as_of_raw:
                summary["skipped"] += 1
                continue
            as_of = date.fromisoformat(str(as_of_raw)[:10])
            if as_of < cutoff:
                summary["skipped"] += 1
                continue

            target_raw = row.get("prediction_target_date")
            target = (
                date.fromisoformat(str(target_raw)[:10])
                if target_raw
                else _prediction_target_date(as_of)
            )
            # Only score once the target day has passed
            if target >= date.today():
                summary["skipped"] += 1
                continue

            ticker = str(row["ticker"])
            actual_price = _close_price_on_or_after(ticker, target)
            if actual_price is None:
                summary["skipped"] += 1
                continue

            current_price = row.get("current_price")
            if current_price is None:
                # Fallback: last value from trailing month history if present
                history = row.get("actual_prices_last_month")
                if isinstance(history, str):
                    try:
                        history = json.loads(history)
                    except json.JSONDecodeError:
                        history = []
                if isinstance(history, list) and history:
                    current_price = float(history[-1])

            predicted_price = float(row.get("predicted_price") or 0.0)
            predicted_return = float(row.get("predicted_return") or 0.0)
            actual_return: float | None = None
            current_price_f: float | None = None
            if isinstance(current_price, int | float) and current_price != 0:
                current_price_f = float(current_price)
                actual_return = (actual_price - current_price_f) / current_price_f
            elif current_price is not None:
                try:
                    current_price_f = float(current_price)
                    if current_price_f != 0:
                        actual_return = (actual_price - current_price_f) / current_price_f
                    else:
                        current_price_f = None
                except (TypeError, ValueError):
                    current_price_f = None

            update_payload = {
                "actual_price": actual_price,
                "actual_return": actual_return,
                "price_error": actual_price - predicted_price,
                "return_error": (
                    None if actual_return is None else actual_return - predicted_return
                ),
                "prediction_target_date": target.isoformat(),
                "current_price": current_price_f,
                "scored_at": datetime.now().isoformat(),
            }
            (
                supabase.table(SUPABASE_TABLE_NAME)
                .update(update_payload)
                .eq("id", row["id"])
                .execute()
            )
            summary["updated"] += 1
        except Exception as exc:
            logger.warning("Failed scoring row %s: %s", row.get("id"), exc)
            summary["errors"] += 1

    logger.info(
        "Outcome scoring complete: attempted=%s updated=%s skipped=%s errors=%s",
        summary["attempted"],
        summary["updated"],
        summary["skipped"],
        summary["errors"],
    )
    return summary


def fetch_scored_outcomes(limit: int = 200) -> list[dict[str, Any]]:
    """Fetch recently scored prediction rows for evaluation reporting."""
    supabase = get_supabase_client()
    if supabase is None:
        raise ValueError(
            "Supabase client not available. Check SUPABASE_URL and SUPABASE_KEY environment variables."
        )
    try:
        response = (
            supabase.table(SUPABASE_TABLE_NAME)
            .select(
                "as_of_date,ticker,predicted_price,predicted_return,actual_price,actual_return,scored_at"
            )
            .not_.is_("actual_price", "null")
            .order("as_of_date", desc=True)
            .limit(limit)
            .execute()
        )
        data = response.data or []
        return [dict(row) for row in data]  # type: ignore[arg-type]
    except Exception as exc:
        logger.warning("Could not fetch scored outcomes: %s", exc)
        return []
