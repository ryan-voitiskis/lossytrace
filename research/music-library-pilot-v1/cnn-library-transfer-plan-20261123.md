# Transfer of the synthetic CNN to the existing paired music pilot

Fixed after the synthetic recipe experiment and before scoring library audio with the CNN. Fit the same pooled CNN once on all 24 synthetic compositions, retaining the six-epoch recipe pilot schedule and its balanced pairs. Apply the final network to the six prespecified excerpts from each local library baseline and each of its six identity-condition codec variants. Average logits over excerpts.

For each codec setting report the counts of strictly higher, tied and lower scores in the 24 matched pairs, and the median paired difference. Compare counts descriptively with the existing synthetic-trained logistic transfer experiment, which used all six processing conditions during training. Differences combine model, training and audio-coverage effects. Upstream library histories are unknown. No library fitting or threshold selection. Stop after this fit and aggregate readback.
