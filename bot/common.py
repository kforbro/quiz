from aiogram.filters.callback_data import CallbackData


class SelectQuizCallbackData(CallbackData, prefix="select_quiz"):
    quiz_id: int


class StopQuizCallbackData(CallbackData, prefix="stop_quiz"):
    quiz_id: int


class StartQuizCallbackData(CallbackData, prefix="start_quiz"):
    quiz_id: int


class InviteQuizCallbackData(CallbackData, prefix="invite_quiz"):
    quiz_id: int


class StatsQuizCallbackData(CallbackData, prefix="stats_quiz"):
    quiz_id: int
