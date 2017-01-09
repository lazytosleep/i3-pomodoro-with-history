import math
from threading import Thread
from pydbus import SessionBus
from gi.repository import GLib
import click
import i3ipc


bus = SessionBus()


def get_notification_proxy():
    return bus.get(
        "org.freedesktop.Notifications", "/org/freedesktop/Notifications")


def get_pomodoro_proxy():
    return bus.get("org.gnome.Pomodoro", "/org/gnome/Pomodoro")


def format_time(seconds):
    return "{minutes:02d}:{seconds:02d}".format(
        minutes=math.floor(seconds / 60),
        seconds=round(seconds % 60)
    )


def format_is_paused(is_paused):
    return " PAUSED " if is_paused else ""


def format_state(state):
    return {
        "pomodoro": "Pomodoro",
        "short-break": "Break",
        "long-break": "Long Break",
    }[state]


def extract_pomodoro_data(pomodoro):
    return {
        "elapsed": pomodoro.Elapsed, "is_paused": pomodoro.IsPaused,
        "duration": pomodoro.StateDuration,
        "remaining": pomodoro.StateDuration - pomodoro.Elapsed,
        "state": pomodoro.State
    }


def format_pomodoro_data(pomodoro_data):
    return {
        "elapsed": format_time(pomodoro_data["elapsed"]),
        "duration": format_time(pomodoro_data["duration"]),
        "remaining": format_time(pomodoro_data["remaining"]),
        "is_paused": format_is_paused(pomodoro_data["is_paused"]),
        "state": format_state(pomodoro_data["state"]),
    }


def format_output(pomodoro_data):
    if pomodoro_data["state"] != "null":
        return "{state} {remaining} {is_paused}".format(**format_pomodoro_data(
            pomodoro_data
        ))
    else:
        return ""


@click.group()
def main():
    pass


@click.command()
def status():
    pomodoro = get_pomodoro_proxy()
    pomodoro_data = extract_pomodoro_data(pomodoro)
    click.echo(format_output(pomodoro_data))


@click.command()
def pause():
    get_pomodoro_proxy().Pause()


@click.command()
def resume():
    get_pomodoro_proxy().Resume()


@click.command()
def start():
    get_pomodoro_proxy().Start()


@click.command()
def stop():
    get_pomodoro_proxy().Stop()


@click.command()
def skip():
    get_pomodoro_proxy().Skip()


@click.command()
def reset():
    get_pomodoro_proxy().Reset()


@click.command()
def toggle():
    pomodoro = get_pomodoro_proxy()
    if pomodoro.IsPaused:
        pomodoro.Resume()
    else:
        pomodoro.Pause()


def dunst_action(action):
    notify = get_notification_proxy()
    notify.Notify("", 0, "", action, "", "", "", 0)


def stop_dunst():
    dunst_action("DUNST_COMMAND_PAUSE")


def start_dunst():
    dunst_action("DUNST_COMMAND_RESUME")


def handle_state(state, old_state):
    if state["name"] == "pomodoro":
        stop_dunst()
    else:
        start_dunst()


def get_focused_workspace(i3):
    return i3.get_tree().find_focused().workspace()


def create_workspace_policy(disabled_during_pomodoro):
    def allowed_workspace(number):
        pomodoro = get_pomodoro_proxy()
        if pomodoro.State == "pomodoro" and pomodoro.IsPaused == False:
            return number != disabled_during_pomodoro
        else:
            return True

    return allowed_workspace


def activate_workspace(i3, name):
    i3.command("workspace %s" % name)


def handle_workspace_focus(i3, i3_state, allowed_workspace):
    def handler(self, e):
        if not allowed_workspace(e.current.num):
            activate_workspace(i3, i3_state["focused_workspace_name"])
        i3_state["focused_workspace_name"] = e.current.name

    return handler


def i3_daemon(disabled_during_pomodoro):
    def daemon():
        workspace_policy = create_workspace_policy(disabled_during_pomodoro)
        i3 = i3ipc.Connection()
        i3_state = {
            "focused_workspace_name": get_focused_workspace(i3).name
        }
        i3.on('workspace::focus', handle_workspace_focus(
            i3, i3_state, workspace_policy))
        i3.main()

    return deamon


def pomodoro_daemon():
    pomodoro = get_pomodoro_proxy()
    pomodoro.StateChanged.connect(handle_state)
    GLib.MainLoop().run()


@click.command()
def deamon():
    disabled_during_pomodoro = [1, 10]
    daemon_commands = [i3_daemon(disabled_during_pomodoro), pomodoro_daemon]
    threads = [Thread(target=command) for command in daemon_commands]
    for thread in threads:
        thread.run()
        thread.join()

main.add_command(status)
main.add_command(pause)
main.add_command(resume)
main.add_command(start)
main.add_command(stop)
main.add_command(skip)
main.add_command(reset)
main.add_command(toggle)
main.add_command(deamon)

if __name__ == "__main__":
    main()
