from __future__ import annotations

import logging

from amplitude_experiment import Experiment
from amplitude_experiment import User

import settings

experiment = Experiment.initialize_local(settings.AMPLITUDE_DEPLOYMENT_KEY)


def is_feature_enabled(
    feature_name: str,
    *,
    user_id: str | None = None,
    device_id: str | None = None,
) -> bool:
    try:
        if not experiment.poller.is_running:
            experiment.start()

        if device_id is None and user_id is None:
            user_id = "1xx"

        user = User(device_id=device_id, user_id=user_id)  # type: ignore[unused-ignore]
        variant = experiment.evaluate_v2(user, {feature_name}).get(feature_name)
        if variant is None:
            return False

        return variant.value == "on"  # type: ignore[no-any-return]
    except Exception:
        logging.exception(
            "Failed to retrieve experiment",
            extra={"feature_name": feature_name},
        )
        return False
