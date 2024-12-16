"""Global objects and variables"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from amplitude import Amplitude
from amplitude import Config as AmplitudeConfig

import settings

if TYPE_CHECKING:
    import aio_pika
    import tornado.web
    from redis.asyncio import Redis

    from objects.banchoConfig import banchoConfig
    from objects.dbPool import DBPool


application: tornado.web.Application | None = None
db: DBPool
redis: Redis[Any]
banchoConf: banchoConfig

groupPrivileges: dict[str, int] = {}
bcrypt_cache: dict[bytes, bytes] = {}

amplitude: Amplitude | None = None
if settings.AMPLITUDE_API_KEY:
    amplitude = Amplitude(
        settings.AMPLITUDE_API_KEY,
        # our user ids start from 1000
        AmplitudeConfig(min_id_length=4),
    )

amqp: aio_pika.abc.AbstractConnection
amqp_channel: aio_pika.abc.AbstractChannel