from future import annotations

from typing import Any, Dict

============================================================

APEX RISK MANAGEMENT ENGINE

============================================================

Responsibilities:

- Calculate Stop Loss

- Calculate TP1 / TP2 / TP3

- Calculate Risk/Reward ratios

- Validate trade levels

This file does NOT:

- fetch market data

- calculate indicators

- score signals

- send Telegram messages

- access PostgreSQL

============================================================

ATR multipliers

DEFAULT_SL_ATR_MULTIPLIER = 1.5

TP1_ATR_MULTIPLIER = 1.5
TP2_ATR_MULTIPLIER = 2.5
TP3_ATR_MULTIPLIER = 4.0

def _safe_float(value: Any, default: float = 0.0) -> float:
"""Safely convert a value to float."""

try:
    result = float(value)

    if result != result:  # NaN check
        return default

    return result

except (TypeError, ValueError):
    return default

def calculate_trade_levels(
*,
entry_price: float,
atr: float,
direction: str,
sl_atr_multiplier: float = DEFAULT_SL_ATR_MULTIPLIER,
) -> Dict[str, float]:
"""
Calculate Stop Loss and three Take Profit levels.

BUY:
    SL below entry
    TP1 above entry
    TP2 above TP1
    TP3 above TP2

SELL:
    SL above entry
    TP1 below entry
    TP2 below TP1
    TP3 below TP2
"""

entry = _safe_float(entry_price)
atr_value = _safe_float(atr)
direction = str(direction).upper().strip()

if entry <= 0:
    raise ValueError("Entry price must be greater than zero.")

if atr_value <= 0:
    raise ValueError("ATR must be greater than zero.")

if direction not in {"BUY", "SELL"}:
    raise ValueError("Direction must be BUY or SELL.")

sl_distance = atr_value * float(sl_atr_multiplier)

tp1_distance = atr_value * TP1_ATR_MULTIPLIER
tp2_distance = atr_value * TP2_ATR_MULTIPLIER
tp3_distance = atr_value * TP3_ATR_MULTIPLIER

if direction == "BUY":
    stop_loss = entry - sl_distance

    tp1 = entry + tp1_distance
    tp2 = entry + tp2_distance
    tp3 = entry + tp3_distance

else:
    stop_loss = entry + sl_distance

    tp1 = entry - tp1_distance
    tp2 = entry - tp2_distance
    tp3 = entry - tp3_distance

levels = {
    "entry_price": entry,
    "stop_loss": stop_loss,
    "tp1": tp1,
    "tp2": tp2,
    "tp3": tp3,
}

if not validate_trade_levels(
    entry_price=entry,
    stop_loss=stop_loss,
    tp1=tp1,
    tp2=tp2,
    tp3=tp3,
    direction=direction,
):
    raise ValueError("Generated trade levels failed validation.")

return levels

def calculate_risk_reward(
*,
entry_price: float,
stop_loss: float,
take_profit: float,
) -> float:
"""
Calculate the Risk/Reward ratio.

Example:
    Risk = 10
    Reward = 20
    Result = 2.0R
"""

entry = _safe_float(entry_price)
sl = _safe_float(stop_loss)
tp = _safe_float(take_profit)

risk = abs(entry - sl)
reward = abs(tp - entry)

if risk <= 0:
    return 0.0

return round(reward / risk, 2)

def calculate_all_risk_rewards(
*,
entry_price: float,
stop_loss: float,
tp1: float,
tp2: float,
tp3: float,
) -> Dict[str, float]:
"""Calculate R:R for all three take-profit targets."""

return {
    "tp1_rr": calculate_risk_reward(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=tp1,
    ),
    "tp2_rr": calculate_risk_reward(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=tp2,
    ),
    "tp3_rr": calculate_risk_reward(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=tp3,
    ),
}

def validate_trade_levels(
*,
entry_price: float,
stop_loss: float,
tp1: float,
tp2: float,
tp3: float,
direction: str,
) -> bool:
"""
Validate that the trade levels are logically positioned.

BUY:
    SL < Entry < TP1 < TP2 < TP3

SELL:
    TP3 < TP2 < TP1 < Entry < SL
"""

entry = _safe_float(entry_price)
sl = _safe_float(stop_loss)
first_tp = _safe_float(tp1)
second_tp = _safe_float(tp2)
third_tp = _safe_float(tp3)

direction = str(direction).upper().strip()

values = [
    entry,
    sl,
    first_tp,
    second_tp,
    third_tp,
]

if any(value <= 0 for value in values):
    return False

if direction == "BUY":
    return (
        sl < entry
        and entry < first_tp
        and first_tp < second_tp
        and second_tp < third_tp
    )

if direction == "SELL":
    return (
        third_tp < second_tp
        and second_tp < first_tp
        and first_tp < entry
        and entry < sl
    )

return False

def calculate_position_risk(
*,
entry_price: float,
stop_loss: float,
risk_amount: float,
) -> Dict[str, float]:
"""
Calculate price risk and an abstract position size.

IMPORTANT:
Position sizing for Forex, crypto spot, futures, and CFDs
uses different contract specifications. Therefore this function
intentionally does NOT pretend that one universal lot-size
formula works for every market.

It returns:
    price_risk
    risk_amount
    units_at_risk

For a simple linear instrument:

    units = risk_amount / price_risk
"""

entry = _safe_float(entry_price)
sl = _safe_float(stop_loss)
capital_risk = _safe_float(risk_amount)

price_risk = abs(entry - sl)

if entry <= 0 or sl <= 0:
    raise ValueError("Entry and Stop Loss must be greater than zero.")

if capital_risk <= 0:
    raise ValueError("Risk amount must be greater than zero.")

if price_risk <= 0:
    raise ValueError("Entry and Stop Loss cannot be equal.")

units = capital_risk / price_risk

return {
    "price_risk": round(price_risk, 8),
    "risk_amount": round(capital_risk, 2),
    "units_at_risk": round(units, 8),
}

def build_risk_profile(
*,
entry_price: float,
atr: float,
direction: str,
sl_atr_multiplier: float = DEFAULT_SL_ATR_MULTIPLIER,
) -> Dict[str, Any]:
"""
Build the complete risk profile for a signal.

This is the main function the signal generator should call.
"""

levels = calculate_trade_levels(
    entry_price=entry_price,
    atr=atr,
    direction=direction,
    sl_atr_multiplier=sl_atr_multiplier,
)

rr = calculate_all_risk_rewards(
    entry_price=levels["entry_price"],
    stop_loss=levels["stop_loss"],
    tp1=levels["tp1"],
    tp2=levels["tp2"],
    tp3=levels["tp3"],
)

return {
    **levels,
    **rr,
    "direction": str(direction).upper(),
    "valid": True,
}

def breakeven_price(entry_price: float) -> float:
"""Return the original entry price used as the breakeven level."""

entry = _safe_float(entry_price)

if entry <= 0:
    raise ValueError("Entry price must be greater than zero.")

return entry

def progress_to_tp(
*,
entry_price: float,
current_price: float,
take_profit: float,
direction: str,
) -> float:
"""
Return progress toward TP as a percentage from 0 to 100.

0%   = entry
50%  = halfway to TP
100% = TP reached
"""

entry = _safe_float(entry_price)
current = _safe_float(current_price)
tp = _safe_float(take_profit)

direction = str(direction).upper().strip()

if entry <= 0 or current <= 0 or tp <= 0:
    return 0.0

if direction == "BUY":
    distance = tp - entry

    if distance <= 0:
        return 0.0

    progress = (current - entry) / distance

elif direction == "SELL":
    distance = entry - tp

    if distance <= 0:
        return 0.0

    progress = (entry - current) / distance

else:
    return 0.0

return round(max(0.0, min(progress, 1.0)) * 100, 2)

def should_move_to_breakeven(
*,
entry_price: float,
current_price: float,
take_profit: float,
direction: str,
trigger_percent: float = 50.0,
) -> bool:
"""Determine whether price has reached the breakeven trigger."""

progress = progress_to_tp(
    entry_price=entry_price,
    current_price=current_price,
    take_profit=take_profit,
    direction=direction,
)

return progress >= float(trigger_percent)
