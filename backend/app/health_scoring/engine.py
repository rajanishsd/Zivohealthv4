from typing import List, Tuple, Optional


def interpolate_piecewise(value: float, anchors: List[Tuple[float, float]], clamp_low: float = 0.0, clamp_high: float = 100.0) -> float:
    """Piecewise linear interpolation. Anchors are sorted by value.

    This engine function is deliberately small and deterministic so it can be
    unit-tested independently of the service layer.
    """
    if not anchors:
        return 0.0
    # Ensure sorted
    pts = sorted(anchors, key=lambda x: x[0])
    # Clamp
    if value <= pts[0][0]:
        return max(clamp_low, min(clamp_high, pts[0][1]))
    if value >= pts[-1][0]:
        return max(clamp_low, min(clamp_high, pts[-1][1]))
    # Find segment
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        if x0 <= value <= x1:
            if x1 == x0:
                return max(clamp_low, min(clamp_high, y1))
            t = (value - x0) / (x1 - x0)
            y = y0 + t * (y1 - y0)
            return max(clamp_low, min(clamp_high, y))
    # Fallback
    return max(clamp_low, min(clamp_high, pts[-1][1]))


def exponential_decay_weight(days_since: float, half_life_days: Optional[float]) -> float:
    """Compute exponential decay weight from days since observation to now.
    If half_life_days is None or <= 0, weight is 1.0.
    """
    if not half_life_days or half_life_days <= 0:
        return 1.0
    # weight = 0.5 ** (days_since / half_life_days)
    try:
        return pow(0.5, float(days_since) / float(half_life_days))
    except Exception:
        return 0.0


