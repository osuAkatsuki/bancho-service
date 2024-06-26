from __future__ import annotations

from collections import defaultdict
from datetime import datetime as dt
from time import time
from typing import Any

import httpx

from common.log import logger

discord_webhook_http_client = httpx.AsyncClient()


class Webhook:
    def __init__(self, url: str, **kwargs: Any) -> None:
        """
        Initialise a Webhook Embed Object.
        """

        self.url = url
        self.msg = kwargs.get("msg")
        self.color = kwargs.get("color") or kwargs.get("colour")
        self.title = kwargs.get("title")
        self.title_url = kwargs.get("title_url")
        self.author = kwargs.get("author")
        self.author_icon = kwargs.get("author_icon")
        self.author_url = kwargs.get("author_url")
        self.desc = kwargs.get("desc")
        self.fields = kwargs.get("fields", [])
        self.image = kwargs.get("image")
        self.thumbnail = kwargs.get("thumbnail")
        self.footer = kwargs.get("footer")
        self.footer_icon = kwargs.get("footer_icon")
        self.ts = kwargs.get("ts")

    def add_field(self, **kwargs: Any) -> None:
        """
        Adds a field to `self.fields`.
        """

        self.fields.append(
            {
                "name": kwargs.get("name"),
                "value": kwargs.get("value"),
                "inline": kwargs.get("inline", True),
            },
        )

    def set_desc(self, desc: str) -> None:
        self.desc = desc

    def set_author(self, **kwargs: Any) -> None:
        self.author = kwargs.get("name")
        self.author_icon = kwargs.get("icon")
        self.author_url = kwargs.get("url")

    def set_title(self, **kwargs: Any) -> None:
        self.title = kwargs.get("title")
        self.title_url = kwargs.get("url")

    def set_thumbnail(self, url: str) -> None:
        self.thumbnail = url

    def set_image(self, url: str) -> None:
        self.image = url

    def set_footer(self, **kwargs: Any) -> None:
        self.footer = kwargs.get("text")
        self.footer_icon = kwargs.get("icon")
        self.ts = str(dt.utcfromtimestamp(time()))

    def del_field(self, index: int) -> None:
        self.fields.pop(index)

    @property
    def json(self) -> dict[str, Any]:
        """
        Formats the data into a payload
        """

        data: dict[str, Any] = {}

        data["embeds"] = []
        embed: dict[str, Any] = defaultdict(dict)
        if self.msg:
            data["content"] = self.msg
        if self.author:
            embed["author"]["name"] = self.author
        if self.author_icon:
            embed["author"]["icon_url"] = self.author_icon
        if self.author_url:
            embed["author"]["url"] = self.author_url
        if self.color:
            embed["color"] = self.color
        if self.desc:
            embed["description"] = self.desc
        if self.title:
            embed["title"] = self.title
        if self.title_url:
            embed["url"] = self.title_url
        if self.image:
            embed["image"]["url"] = self.image
        if self.thumbnail:
            embed["thumbnail"]["url"] = self.thumbnail
        if self.footer:
            embed["footer"]["text"] = self.footer
        if self.footer_icon:
            embed["footer"]["icon_url"] = self.footer_icon
        if self.ts:
            embed["timestamp"] = self.ts

        if self.fields:
            embed["fields"] = []
            for field in self.fields:
                f = {}
                f["name"] = field["name"]
                f["value"] = field["value"]
                f["inline"] = field.get("inline", True)
                embed["fields"].append(f)

        data["embeds"].append(dict(embed))

        empty = all(not d for d in data["embeds"])

        if empty and "content" not in data:
            logger.error("Attempted to post an empty payload in a discord webhook")
        if empty:
            data["embeds"] = []

        return data

    async def post(self) -> None:
        """
        Send the JSON formated object to the specified `self.url`.
        """

        response = await discord_webhook_http_client.post(
            self.url,
            json=self.json,
        )

        if response.status_code not in range(200, 300):
            logger.error(
                "Failed to post discord webhook.",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
        else:
            logger.info("Posted webhook to Discord.")
