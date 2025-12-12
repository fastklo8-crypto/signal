from analyzer import Signal

def to_text(sig: Signal) -> str:
    reason_str = "; ".join([f"{r}" for r in sig.reasons])
    header = f"{sig.strength} Сигнал  {sig.symbol} ({sig.tf})  {sig.side}"
    lines = [
        header,
        f"ТВХ: {sig.entry}   SL: {sig.sl}   TP: {sig.tp}",
        f"Причина: score={sig.score}; {reason_str}",
        f"Реком. сумма: ${sig.rec_usd}",
        f"Дата: {sig.timestamp_utc}",
    ]
    return "\n".join(lines)
