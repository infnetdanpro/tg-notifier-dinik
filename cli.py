import click


@click.group()
def entire_group():
    ...


@click.group()
def worker():
    """
    Manage/Run workers
    """


@worker.command()
def vkplay():
    """
    Run vkplay.live workers for checking live statutes
    python cli.py worker vkplay
    """
    from web.worker.vkplay import main

    main()


@worker.command()
def vkplay_send_notifications():
    from web.worker.vkplay_notifications import main

    main()


@worker.command()
def goodgame():
    from web.worker.goodgame import main

    main()


@worker.command()
def goodgame_send_notifications():
    from web.worker.goodgame_notifications import main

    main()


entire_group.add_command(worker)


if __name__ == "__main__":
    entire_group()
