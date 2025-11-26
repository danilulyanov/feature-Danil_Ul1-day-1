from aiogram.fsm.state import State, StatesGroup

CANCEL_COMMANDS = {
    "/cancel",
    "cancel",
    "/exit",
    "exit",
    "/отмена",
    "отмена",
    "/выход",
    "выход",
}


class EditProfile(StatesGroup):
    city = State()
    position = State()
    name = State()
    skills = State()
    resume = State()
    llm = State()


class EditSearchFilters(StatesGroup):
    min_salary = State()


class EditPreferences(StatesGroup):
    language = State()
    schedule_time = State()
    timezone = State()
