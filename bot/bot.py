import asyncio

from twitchAPI.eventsub import EventSub
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch as TwitchService

from config import config

TARGET_USERNAME = "danpro_infnet"


async def on_stream_online(data: dict):
    # our event happend, lets do things with the data we got!
    print(data)


async def eventsub_example():
    # create the api instance and get the ID of the target user
    twitch = await TwitchService(config.APP_ID, config.APP_SECRET)
    user = await first(twitch.get_users(logins=TARGET_USERNAME))

    # basic setup, will run on port 8080 and a reverse proxy takes care of the h                                                                                                                     ttps and certificate
    event_sub = EventSub(config.EVENTSUB_URL, config.APP_ID, 8080, twitch)

    # unsubscribe from all old events that might still be there
    # this will ensure we have a clean slate
    await event_sub.unsubscribe_all()
    # start the eventsub client
    # event_sub.start()
    # # subscribing to the desired eventsub hook for our user
    # # the given function will be called every time this event is triggered
    # await event_sub.listen_stream_online(
    #     broadcaster_user_id=user.id, callback=on_stream_online
    # )
    # eventsub will run in its own process
    # so lets just wait for user input before shutting it all down again
    try:
        input("press Enter to shut down...")
    finally:
        # stopping both eventsub as well as gracefully closing the connection to                                                                                                                      the API
        await event_sub.stop()
        await twitch.close()
    print("done")


if __name__ == "__main__":
    # lets run our example
    asyncio.run(eventsub_example())
