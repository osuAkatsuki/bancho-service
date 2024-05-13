from __future__ import annotations
from typing import TypedDict

import redis.asyncio as redis

from common.log import logger
from common.redis import generalPubSubHandler


class RedisMessage(TypedDict):
    type: str
    pattern: bytes | None
    channel: bytes | None
    data: bytes | None


class listener:
    def __init__(
        self,
        redis_connection: redis.Redis,
        handlers: dict[str, generalPubSubHandler.generalPubSubHandler],
    ):
        """
        Initialize a set of redis pubSub listeners

        :param r: redis instance (usually glob.redis)
        :param handlers: dictionary with the following structure:
        ```
        {
            "redis_channel_name": handler,
            ...
        }
        ```
        Where handler is:
        - 	An object of a class that inherits common.redis.generalPubSubHandler.
            You can create custom behaviors for your handlers by overwriting the `handle(self, data)` method,
            that will be called when that handler receives some data.

        - 	A function *object (not call)* that accepts one argument, that'll be the data received through the channel.
            This is useful if you want to make some simple handlers through a lambda, without having to create a class.
        """
        self.redis_connection = redis_connection
        self.handlers = handlers

    async def processItem(self, item: RedisMessage) -> None:
        """
        Processes a pubSub item by calling channel's handler

        :param item: incoming data
        :return:
        """
        if item["type"] == "message":
            # Process the message only if the channel has received a message
            # Decode the message
            assert item["channel"] is not None
            channel = item["channel"].decode()

            # Make sure the handler exists
            if channel in self.handlers:
                if "cached_stats" not in channel:
                    logger.info(
                        "Handling redis pubsub item",
                        extra={
                            "channel": channel,
                            "data": item["data"],
                        },
                    )

                if isinstance(
                    self.handlers[channel],
                    generalPubSubHandler.generalPubSubHandler,
                ):
                    # Handler class
                    await self.handlers[channel].handle(item["data"])
                # else:
                #     # Function
                #     await self.handlers[channel](item["data"])

    async def run(self):
        """
        Listen for data on incoming channels and process it.
        Runs forever.

        :return:
        """
        pubsub = self.redis_connection.pubsub()

        channels = list(self.handlers.keys())
        await pubsub.subscribe(*channels)
        logger.info(
            "Subscribed to redis pubsub channels",
            extra={"channels": channels},
        )

        async for item in pubsub.listen():
            try:
                await self.processItem(item)
            except Exception:
                logger.exception(
                    "An error occurred while processing a pubsub item",
                    extra={"item": item},
                )
