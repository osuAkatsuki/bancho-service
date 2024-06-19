from __future__ import annotations

from typing import Any

from common import generalUtils
from constants import serverPackets
from objects import channelList
from objects import glob
from objects import stream
from objects import stream_messages


class banchoConfig:
    """
    Class that loads settings from bancho_settings db table
    """

    config: dict[str, Any] = {
        "banchoMaintenance": False,
        "freeDirect": True,
        "menuIcon": "",
        "loginNotification": "",
    }

    async def loadSettings(self) -> None:
        """
        (re)load bancho_settings from DB and set values in config array
        """
        bancho_maintenance_rec = await glob.db.fetch(
            "SELECT value_int FROM bancho_settings WHERE name = 'bancho_maintenance'",
        )
        assert bancho_maintenance_rec is not None
        self.config["banchoMaintenance"] = generalUtils.stringToBool(
            bancho_maintenance_rec["value_int"],
        )
        free_direct_rec = await glob.db.fetch(
            "SELECT value_int FROM bancho_settings WHERE name = 'free_direct'",
        )
        assert free_direct_rec is not None
        self.config["freeDirect"] = generalUtils.stringToBool(
            free_direct_rec["value_int"],
        )
        mainMenuIcon = await glob.db.fetch(
            "SELECT file_id, url FROM main_menu_icons WHERE is_current = 1 LIMIT 1",
        )
        if mainMenuIcon is None:
            self.config["menuIcon"] = ""
        else:
            imageURL = mainMenuIcon["file_id"]
            self.config["menuIcon"] = f"{imageURL}|{mainMenuIcon['url']}"

        login_notification_rec = await glob.db.fetch(
            "SELECT value_string FROM bancho_settings WHERE name = 'login_notification'",
        )
        assert login_notification_rec is not None
        self.config["loginNotification"] = login_notification_rec["value_string"]

    async def setMaintenance(self, maintenance: bool) -> None:
        """
        Turn on/off bancho maintenance mode. Write new value to db too

        maintenance -- if True, turn on maintenance mode. If false, turn it off
        """
        self.config["banchoMaintenance"] = maintenance
        await glob.db.execute(
            "UPDATE bancho_settings SET value_int = %s WHERE name = 'bancho_maintenance'",
            [int(maintenance)],
        )

    async def reload(self) -> None:
        # Reload settings from bancho_settings
        await glob.banchoConf.loadSettings()

        # Reload channels too
        await channelList.loadChannels()

        # Send new channels and new bottom icon to everyone
        await stream_messages.broadcast_data(
            "main",
            serverPackets.mainMenuIcon(glob.banchoConf.config["menuIcon"]),
        )
        await stream_messages.broadcast_data("main", serverPackets.channelInfoEnd)
        for channel in await channelList.getChannels():
            if channel["public_read"] and not channel["instance"]:
                client_count = await stream.get_client_count(f"chat/{channel['name']}")
                packet_data = serverPackets.channelInfo(
                    channel["name"],
                    channel["description"],
                    client_count,
                )
                await stream_messages.broadcast_data("main", packet_data)
