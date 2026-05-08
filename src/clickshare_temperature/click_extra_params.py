
import click


from click_extra import (
    TimerOption,
    ColorOption,
    ThemeOption,
    ShowParamsOption,
    ExtraVersionOption,
)


def get_extra_params() -> list[click.Option]:
    """Get the extra parameters for the ClickShare CLI commands."""
    return [
        TimerOption(),
        ColorOption(),
        ThemeOption(),
        ShowParamsOption(),
        ExtraVersionOption(),
    ]
