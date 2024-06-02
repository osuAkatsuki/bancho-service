from amplitude_experiment import Experiment, User
import settings

experiment = Experiment.initialize_local(settings.AMPLITUDE_DEPLOYMENT_KEY)

def is_feature_enabled(
    feature_name: str,
    *,
    user_id: str | None = None,
    device_id: str | None = None,
) -> bool:
    if not experiment.poller.is_running:
        experiment.start()

    if device_id is None and user_id is None:
        user_id = "1xx"

    user = User(device_id=device_id, user_id=user_id) # type: ignore
    variant = experiment.evaluate_v2(user, {feature_name}).get(feature_name)
    if variant is None:
        return False

    return variant.value == "on"
