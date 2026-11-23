# Offline single-file test outcome

The ranking objective failed the prespecified pilot criteria. The original CNN flagged one of 64 clean compositions and five of 384 encoded copies. The ranking CNN flagged zero files in both groups. Class-balanced coverage fell from 12.1% to 7.8%. All five baseline detections came from the pulse-lead recipe. The ranking model also produced fewer positive paired changes at every codec setting on the secondary commercial-library check.

A post hoc diagnostic used the saved evaluation scores with no refitting or threshold changes. For each encoded file we compared its score with its own clean source. The original CNN scored the encode higher in 330/384 comparisons, and the ranking CNN in 378/384. Across all encoded–clean combinations, giving ties half credit, their respective ROC AUCs were 0.524 and 0.533. These descriptive values include related codec variants. They explain how a stronger paired response can coexist with poor single-file discrimination.

Verification covered the complete recipe/cell/state matrices, 672 unique decoded PCM hashes across calibration and evaluation, encoded and baseline file hashes, threshold order statistics and all aggregate decision counts. Two calibration cases reproduced their clean renders and both checkpoint scores exactly. The original CNN reproduced its earlier six library pair counts. The locked thresholds file had SHA-256 `f15d0e4a885a5cc308b09999f3509c8d3a9db68d622b630eb79add29ffb1cdd2`.

The four evaluation recipes share a sequencer and have now been examined. These results describe the two tested pipelines on this procedural population. They support ending this candidate comparison and retaining the measurement-only inspector as the current user-facing output.
