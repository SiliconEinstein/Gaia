from galileo_v0_5 import (
    aristotle_model,
    daily_observation,
    medium_model,
)

PRIORS = {
    daily_observation: (
        0.90,
        "The everyday observation is treated as familiar empirical background, "
        "not as a new vacuum experiment.",
    ),
    aristotle_model: (
        0.50,
        "Before the thought experiment, keep the weight-speed model neutral.",
    ),
    medium_model: (
        0.50,
        "Before the thought experiment, keep the medium-resistance model neutral.",
    ),
}
