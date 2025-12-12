import os
import matplotlib.pyplot as plt

def save_signal_chart(df, symbol: str, tf: str, entry: float, sl: float, tp: float, out_dir: str = "out") -> str:
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10,5))
    ax.plot(df.index, df["close"])
    ax.axhline(entry, linestyle="--")
    ax.axhline(sl, linestyle=":")
    ax.axhline(tp, linestyle=":")
    ax.set_title(f"{symbol} {tf}")
    ax.set_xlabel("Index")
    ax.set_ylabel("Price")
    path = os.path.join(out_dir, f"{symbol}_{tf}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
