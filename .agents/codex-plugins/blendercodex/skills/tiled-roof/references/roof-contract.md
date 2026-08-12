# Tiled-roof executor contract

A build domain supplies `roofObject`, `ownerObject`, `kind`, `eave`, `ridge`, `ridgeDirection`, and `ridgeSpan`. A `gable_mirror` domain also supplies `mirrorAxis` (`0`, `1`, or `2`). An `l_boolean` domain supplies `cutterObject`.

The `traditional_gray_v1` profile uses closed editable sources:

- pan: `0.50 × 0.28 × 0.032 m`, curvature `0.035`, 6 cross segments;
- cover: `0.51 × 0.15 × 0.030 m`, curvature `0.075`, 8 segments;
- ridge: `0.52 × 0.36 × 0.035 m`, curvature `0.14`, 10 segments;
- target row/column/ridge pitches: `0.34 / 0.31 / 0.38 m`.

Counts use `ceil((span-module)/target_pitch)+1`; spacing is then recomputed to cover the usable span exactly. Pan and cover objects keep two unapplied Array modifiers. Symmetric gables add Mirror last. L-roof domains add Boolean Difference with the MANIFOLD solver last. Ridge tiles remain independent and use one Array.
