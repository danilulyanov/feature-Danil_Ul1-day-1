from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def search_settings_keyboard(filters: dict | None, lang: str) -> InlineKeyboardMarkup:
    remote = bool(filters.get("remote_only")) if filters else False

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.set_salary", lang),
                    callback_data="search_set_salary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.remote", lang).format(
                        state=(t("profile.on_tick", lang) if remote else t("profile.off", lang))
                    ),
                    callback_data="search_toggle_remote",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.fresh_off", lang),
                    callback_data="search_freshness:clear",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.fresh_1d", lang),
                    callback_data="search_freshness:1",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.fresh_2d", lang),
                    callback_data="search_freshness:2",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.fresh_3d", lang),
                    callback_data="search_freshness:3",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.employment", lang),
                    callback_data="search_employment_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.experience", lang),
                    callback_data="search_experience_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.clear_filters", lang),
                    callback_data="search_clear_filters",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.back_profile", lang),
                    callback_data="search_back_profile",
                )
            ],
        ]
    )


def employment_keyboard(current: str | None, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    labels = {
        "full": t("profile.employment.full", lang),
        "part": t("profile.employment.part", lang),
        "project": t("profile.employment.project", lang),
        "volunteer": t("profile.employment.volunteer", lang),
        "probation": t("profile.employment.probation", lang),
    }
    for key, label in labels.items():
        marker = "✅ " if key == current else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{label}",
                    callback_data=f"search_set_employment:{key}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=t("profile.buttons.clear_employment", lang),
                callback_data="search_set_employment:clear",
            )
        ]
    )
    buttons.append([InlineKeyboardButton(text=t("profile.buttons.back", lang), callback_data="search_settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def experience_keyboard(current: str | None, lang: str) -> InlineKeyboardMarkup:
    labels = [
        ("noExperience", t("profile.experience.noExperience", lang)),
        ("between1And3", t("profile.experience.between1And3", lang)),
        ("between3And6", t("profile.experience.between3And6", lang)),
        ("moreThan6", t("profile.experience.moreThan6", lang)),
    ]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in labels:
        marker = "✅ " if key == current else ""
        row.append(
            InlineKeyboardButton(
                text=f"{marker}{label}",
                callback_data=f"search_set_experience:{key}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text=t("profile.buttons.clear_experience", lang),
                callback_data="search_set_experience:clear",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=t("profile.buttons.back", lang), callback_data="search_settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def preferences_keyboard(has_prompt: bool, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.change_language", lang),
                    callback_data="prefs_lang_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.back_profile", lang),
                    callback_data="prefs_back_profile",
                ),
            ],
        ]
    )


def skills_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_skills", lang),
                    callback_data="edit_skills",
                )
            ],
            [InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="skills_back_profile")],
        ]
    )


def llm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.llm_edit", lang),
                    callback_data="llm_edit",
                )
            ],
            [InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="llm_back_profile")],
        ]
    )


def profile_keyboard(lang: str, skills_count: int = 0, skills_preview: str | None = None) -> InlineKeyboardMarkup:
    skills_button_label = t("profile.buttons.skills_menu", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("profile.buttons.edit_name", lang), callback_data="edit_name"),
                InlineKeyboardButton(text=t("profile.buttons.edit_city", lang), callback_data="edit_city"),
            ],
            [
                InlineKeyboardButton(text=t("profile.buttons.edit_position", lang), callback_data="edit_position"),
                InlineKeyboardButton(
                    text=skills_button_label,
                    callback_data="skills_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_resume", lang),
                    callback_data="edit_resume",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.llm_settings", lang),
                    callback_data="llm_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.search_settings", lang),
                    callback_data="search_settings",
                ),
                InlineKeyboardButton(text=t("profile.buttons.preferences", lang), callback_data="prefs_menu"),
            ],
        ]
    )
