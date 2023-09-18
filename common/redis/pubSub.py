from __future__ import annotations

import redis.asyncio as redis

from common.log import logUtils as log
from common.redis import generalPubSubHandler


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

    async def processItem(self, item):
        """
        Processes a pubSub item by calling channel's handler

        :param item: incoming data
        :return:
        """
        if item["type"] == "message":
            # Process the message only if the channel has received a message
            # Decode the message
            item["channel"] = item["channel"].decode("utf-8")

            # Make sure the handler exists
            if item["channel"] in self.handlers:
                if "cached_stats" not in item["channel"]:
                    log.info(
                        "Redis pubsub: {} <- {} ".format(item["channel"], item["data"]),
                    )

                if isinstance(
                    self.handlers[item["channel"]],
                    generalPubSubHandler.generalPubSubHandler,
                ):
                    # Handler class
                    await self.handlers[item["channel"]].handle(item["data"])
                # else:
                #     # Function
                #     await self.handlers[item["channel"]](item["data"])

    async def run(self):
        """
        Listen for data on incoming channels and process it.
        Runs forever.

        :return:
        """
        pubsub = self.redis_connection.pubsub()

        channels = list(self.handlers.keys())
        await pubsub.subscribe(*channels)
        log.info(f"Subscribed to redis pubsub channels: {channels}")

        async for item in pubsub.listen():
            await self.processItem(item)
